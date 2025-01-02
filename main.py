import streamlit as st
import PyPDF2
from PyPDF2 import PdfMerger
import tempfile
import os
from streamlit_pdf_viewer import pdf_viewer
# 修正点1: streamlit-sortablesをインポート
from streamlit_sortables import sort_items
import fitz
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
import gc
from datetime import datetime 

def init_session_state():
    """セッション状態の初期化"""
    if 'pdf_files' not in st.session_state:
        st.session_state.pdf_files = []
        st.session_state.pdf_names = []
        st.session_state.temp_files = []
        st.session_state.current_page = {}  # ページ状態の保持用

def create_thumbnail(pdf_path, page_num, scale=0.2):
    """PDFページのサムネイルを生成（メモリ最適化版）"""
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        gc.collect()  # メモリ解放
        return img
    except Exception as e:
        st.error(f"サムネイル生成エラー: {str(e)}")
        return None

def save_uploaded_file(uploaded_file):
    """アップロードされたファイルを一時ファイルとして保存"""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            st.session_state.temp_files.append(tmp_file.name)
            return tmp_file.name
    except Exception as e:
        st.error(f"ファイルの保存に失敗しました: {str(e)}")
        return None
    
def save_image_as_pdf(image_file):
    """画像ファイルをPDFに変換して保存"""
    try:
        image = Image.open(image_file)
        if image.mode == "RGBA":
            image = image.convert("RGB")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            image.save(tmp_file.name, "PDF", resolution=100.0)
            st.session_state.temp_files.append(tmp_file.name)
            return tmp_file.name
    except Exception as e:
        st.error(f"画像のPDF変換に失敗しました: {str(e)}")
        return None

def merge_pdfs(pdf_paths, progress_bar=None):
    """PDFファイルの結合"""
    merger = PdfMerger()
    try:
        for i, pdf_path in enumerate(pdf_paths):
            merger.append(pdf_path)
            if progress_bar:
                progress_bar.progress((i + 1) / len(pdf_paths))
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_output:
            merger.write(tmp_output)
            merger.close()
            return tmp_output.name
    except Exception as e:
        st.error(f"PDFの結合に失敗しました: {str(e)}")
        return None

def cleanup_temp_files():
    """一時ファイルの削除"""
    # 現在のセッションで使用中のファイルを取得
    current_files = set(st.session_state.pdf_files)
    temp_files = set(st.session_state.temp_files)
    # 使用されていないファイルのみ削除
    files_to_delete = temp_files - current_files
    for temp_file in files_to_delete:
        try:
            os.unlink(temp_file)
            st.session_state.temp_files.remove(temp_file)
        except Exception as e:
            pass

def display_pdf_with_navigation(pdf_path, pdf_name):
    """改善されたPDFビューア（メモリ最適化・エラーハンドリング強化版）"""
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        # ページナビゲーション
        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            current_page = st.session_state.current_page.get(pdf_name, 1)
            page_num = st.number_input(
                "ページ番号",
                min_value=1,
                max_value=total_pages,
                value=current_page,
                key=f"page_{pdf_name}"
            )
            st.session_state.current_page[pdf_name] = page_num

        with col2:
            st.write(f"全{total_pages}ページ")
            if total_pages > 30:
                st.warning("⚠️ 大規模PDFファイルです。表示に時間がかかる場合があります。")

        # サムネイルグリッド表示（最適化版）
        with st.expander("サムネイル表示", expanded=False):
            num_thumbnails = min(5, total_pages)
            thumbnail_cols = st.columns(num_thumbnails)
            
            start_page = max(1, page_num - num_thumbnails//2)
            
            for i, col in enumerate(thumbnail_cols):
                page_idx = start_page + i - 1
                if 0 <= page_idx < total_pages:
                    with col:
                        with st.spinner(f"サムネイル生成中 {page_idx + 1}"):
                            thumbnail = create_thumbnail(pdf_path, page_idx)
                            if thumbnail:
                                st.image(thumbnail, caption=f"P.{page_idx + 1}", use_container_width=True)
                                if st.button("表示", key=f"thumb_{pdf_name}_{page_idx}"):
                                    st.session_state.current_page[pdf_name] = page_idx + 1
                                    st.rerun()

        # 現在のページのプレビュー（最適化版）
        with st.expander("プレビュー", expanded=True):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                writer = PdfWriter()
                writer.add_page(reader.pages[page_num - 1])
                writer.write(tmp_file)
                tmp_file.flush()
                pdf_viewer(tmp_file.name, width=700)
                os.unlink(tmp_file.name)
                
        # メモリ解放
        reader = None
        gc.collect()

    except Exception as e:
        st.error(f"PDFの表示中にエラーが発生しました: {str(e)}")
        st.info("PDFファイルが破損しているか、アクセスできない可能性があります。")

def main():
    st.title("PDF結合アプリケーション")
    
    # メモリ使用量の表示（開発用）
    if st.checkbox("メモリ使用状況を表示", value=False):
        import psutil
        process = psutil.Process()
        st.write(f"現在のメモリ使用量: {process.memory_info().rss / 1024 / 1024:.2f} MB")

    init_session_state()

    # ファイルアップロード
    uploaded_files = st.file_uploader(
        "PDFまたは画像ファイルを選択してください（複数選択可）",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    if uploaded_files:
        # 新規ファイルの追加
        new_files = [f for f in uploaded_files if f.name not in st.session_state.pdf_names]
        for file in new_files:
            if file.type in ['application/pdf']:
                temp_path = save_uploaded_file(file)
            elif file.type in ['image/jpeg', 'image/png']:
                temp_path = save_image_as_pdf(file)
            else:
                st.warning(f"サポートされていないファイル形式です: {file.type}")
                continue
            if temp_path:
                st.session_state.pdf_files.append(temp_path)
                st.session_state.pdf_names.append(file.name)

    if st.session_state.pdf_files:
        st.write("**PDFファイルの並び替えと管理:**")
        
        # ドラッグ&ドロップでファイルの順序を変更
        st.write("以下のリストをドラッグ&ドロップしてファイルの順序を変更できます。")
        new_order = sort_items(st.session_state.pdf_names)

        # ファイルリストの順序を更新
        if new_order != st.session_state.pdf_names:
            new_files = []
            new_names = []
            for name in new_order:
                idx = st.session_state.pdf_names.index(name)
                new_files.append(st.session_state.pdf_files[idx])
                new_names.append(name)
            st.session_state.pdf_files = new_files
            st.session_state.pdf_names = new_names

        # プレビューと操作UI
        for i, (pdf_path, pdf_name) in enumerate(zip(st.session_state.pdf_files, st.session_state.pdf_names)):
            st.write(f"**{pdf_name}**")
            col1, col2 = st.columns([4, 1])
            
            with col1:
                display_pdf_with_navigation(pdf_path, pdf_name)

        # PDF結合処理
        if st.button("PDFを結合"):
            if len(st.session_state.pdf_files) > 0:
                progress_bar = st.progress(0)
                st.write("PDFを結合中...")
                
                merged_pdf_path = merge_pdfs(st.session_state.pdf_files, progress_bar)
                if merged_pdf_path:
                    st.success("PDF結合が完了しました！")

                    # filenameにはdateで日付を入れる
                    file_neme = f"merged_pdf_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                    
                    with open(merged_pdf_path, "rb") as f:
                        st.download_button(
                            "結合したPDFをダウンロード",
                            f,
                            file_name=file_neme,
                            mime="application/pdf"
                        )
                    
                    # 結合後の一時ファイルを削除
                    try:
                        os.unlink(merged_pdf_path)
                    except:
                        pass

    # 一時ファイルのクリーンアップ
    cleanup_temp_files()

if __name__ == "__main__":
    main()