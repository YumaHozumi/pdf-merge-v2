import streamlit as st
import PyPDF2
from PyPDF2 import PdfMerger
import tempfile
import os
from streamlit_pdf_viewer import pdf_viewer
from streamlit_sortables import sort_items
import fitz
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import gc
from datetime import datetime

def init_session_state():
    """セッション状態の初期化を行う"""
    if 'pdf_files' not in st.session_state:
        st.session_state.pdf_files = []
        st.session_state.pdf_names = []
        st.session_state.temp_files = []
        st.session_state.current_page = {}  # ページ状態の保持用

def create_thumbnail(pdf_path, page_num, scale=0.2):
    """PDFページのサムネイルを生成する

    Args:
        pdf_path (str): PDFファイルのパス
        page_num (int): ページ番号（0始まり）
        scale (float, optional): サムネイルの拡大縮小比率. Defaults to 0.2.

    Returns:
        Image or None: 生成されたサムネイル画像、エラー時はNone
    """
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
    """アップロードされたファイルを一時ファイルとして保存する

    Args:
        uploaded_file (UploadedFile): アップロードされたファイルオブジェクト

    Returns:
        str or None: 保存された一時ファイルのパス、エラー時はNone
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            st.session_state.temp_files.append(tmp_file.name)
            return tmp_file.name
    except Exception as e:
        st.error(f"ファイルの保存に失敗しました: {str(e)}")
        return None

def save_image_as_pdf(image_file, preserve_resolution=True):
    """画像ファイルをPDFに変換して保存する

    Args:
        image_file (UploadedFile): アップロードされた画像ファイルオブジェクト
        preserve_resolution (bool, optional): 解像度を保持するかどうか. Defaults to True.

    Returns:
        str or None: 保存されたPDFファイルのパス、エラー時はNone
    """
    try:
        if preserve_resolution:
            # 解像度を保持するバージョン（img2pdfを使用）
            import img2pdf
            # 画像をバイトデータとして読み込む
            img_bytes = image_file.read()
            # RGBAの場合はRGBに変換
            image = Image.open(image_file)
            if image.mode == "RGBA":
                image = image.convert("RGB")
                # 変換後の画像をバイトデータにする
                from io import BytesIO
                img_byte_arr = BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_bytes = img_byte_arr.getvalue()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                pdf_bytes = img2pdf.convert(img_bytes)
                tmp_file.write(pdf_bytes)
                st.session_state.temp_files.append(tmp_file.name)
                return tmp_file.name
        else:
            # 解像度を落とすバージョン（Pillowを使用）
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
    """PDFファイルの結合を行う

    Args:
        pdf_paths (list): 結合するPDFファイルのパスリスト
        progress_bar (Progress or None, optional): 進行状況を表示するプログレスバー. Defaults to None.

    Returns:
        str or None: 結合されたPDFファイルのパス、エラー時はNone
    """
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
    """一時ファイルの削除を行う"""
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
    """PDFのページナビゲーションと表示を行う

    Args:
        pdf_path (str): PDFファイルのパス
        pdf_name (str): PDFファイルの名前
    """
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

        # サムネイルグリッド表示
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
                                    st.experimental_rerun()

        # 現在のページのプレビュー
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

def display_memory_usage():
    """メモリ使用量を表示する"""
    if st.checkbox("メモリ使用状況を表示", value=False):
        import psutil
        process = psutil.Process()
        st.write(f"現在のメモリ使用量: {process.memory_info().rss / 1024 / 1024:.2f} MB")

def synchronize_session_state(uploaded_files):
    """セッション状態を現在のアップロード状況に合わせて更新する

    Args:
        uploaded_files (list): 現在アップロードされたファイルのリスト
    """
    if uploaded_files is not None:
        current_uploaded_file_names = [file.name for file in uploaded_files]
        
        # セッション状態のファイルリストを現在のアップロード状態に合わせて更新
        pdf_names_to_keep = []
        pdf_files_to_keep = []
        for name, path in zip(st.session_state.pdf_names, st.session_state.pdf_files):
            if name in current_uploaded_file_names:
                pdf_names_to_keep.append(name)
                pdf_files_to_keep.append(path)
            else:
                # 一時ファイルを削除
                try:
                    os.unlink(path)
                except:
                    pass
        st.session_state.pdf_names = pdf_names_to_keep
        st.session_state.pdf_files = pdf_files_to_keep
    else:
        # すべてのファイルが削除された場合、セッション状態をクリア
        st.session_state.pdf_names = []
        st.session_state.pdf_files = []
        st.session_state.temp_files = []

def process_uploaded_files(uploaded_files, preserve_resolution):
    """アップロードされた新規ファイルを処理する

    Args:
        uploaded_files (list): アップロードされたファイルのリスト
    """
    if uploaded_files:
        # 新規ファイルの追加
        new_files = [f for f in uploaded_files if f.name not in st.session_state.pdf_names]
        for file in new_files:
            if file.type in ['application/pdf']:
                temp_path = save_uploaded_file(file)
            elif file.type in ['image/jpeg', 'image/png']:
                temp_path = save_image_as_pdf(file, preserve_resolution)
            else:
                st.warning(f"サポートされていないファイル形式です: {file.type}")
                continue
            if temp_path:
                st.session_state.pdf_files.append(temp_path)
                st.session_state.pdf_names.append(file.name)

def display_pdf_management_ui():
    """PDFファイルの並び替えとプレビューを表示するUIを構築する"""
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
        for pdf_path, pdf_name in zip(st.session_state.pdf_files, st.session_state.pdf_names):
            st.write(f"**{pdf_name}**")
            col1, col2 = st.columns([4, 1])
            
            with col1:
                display_pdf_with_navigation(pdf_path, pdf_name)

def display_download_button():
    """サイドバーにダウンロードボタンを表示する"""
    if st.session_state.get('merged_pdf_bytes'):
        st.sidebar.write("## 結合したPDFをダウンロード")
        st.sidebar.download_button(
            "ダウンロード",
            data=st.session_state.merged_pdf_bytes,
            file_name=st.session_state.merged_file_name,
            mime="application/pdf"
        )

def process_pdf_merge():
    """PDF結合処理を実行する"""
    # ボタンをサイドバーに配置
    merge_disabled = not bool(st.session_state.pdf_files)
    if st.sidebar.button("PDFを結合", disabled=merge_disabled):
        with st.spinner("PDFを結合中..."):
            progress_bar = st.sidebar.progress(0)
            merged_pdf_path = merge_pdfs(st.session_state.pdf_files, progress_bar)
            if merged_pdf_path:
                st.sidebar.success("PDF結合が完了しました！")
                st.session_state.merged_file_name = f"merged_pdf_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"

                # 結合したPDFをバイトデータとして読み込み、セッション状態に保存
                with open(merged_pdf_path, "rb") as f:
                    st.session_state.merged_pdf_bytes = f.read()
                
                # 結合後の一時ファイルを削除
                try:
                    os.unlink(merged_pdf_path)
                except:
                    pass

def main():
    """メイン関数"""
    st.title("PDF結合アプリケーション")

    init_session_state()

    # 画像の解像度オプションを選択
    st.sidebar.write("**画像のPDF変換オプション**")
    preserve_resolution = st.sidebar.radio(
        "画像をPDFに変換する際の解像度を選択してください。",
        ('元の解像度を保持する', '解像度を下げる'),
        index=0
    )
    preserve_resolution = (preserve_resolution == '元の解像度を保持する')

    # ファイルアップロード
    uploaded_files = st.file_uploader(
        "PDFまたは画像ファイルを選択してください（複数選択可）",
        type=["pdf", "jpg", "jpeg", "png"],
        accept_multiple_files=True
    )

    synchronize_session_state(uploaded_files)
    process_uploaded_files(uploaded_files, preserve_resolution)
    display_pdf_management_ui()
    process_pdf_merge()
    display_download_button()

    # 一時ファイルのクリーンアップ
    cleanup_temp_files()

if __name__ == "__main__":
    main()