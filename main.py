import streamlit as st
import PyPDF2
from PyPDF2 import PdfMerger
import tempfile
import os
from streamlit_pdf_viewer import pdf_viewer
# 修正点1: streamlit-sortablesをインポート
from streamlit_sortables import sort_items

def init_session_state():
    """セッション状態の初期化"""
    if 'pdf_files' not in st.session_state:
        st.session_state.pdf_files = []
        st.session_state.pdf_names = []
        st.session_state.temp_files = []

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

def main():
    st.title("PDF結合アプリケーション")
    init_session_state()

    # ファイルアップロード
    uploaded_files = st.file_uploader(
        "PDFファイルを選択してください（複数選択可）",
        type="pdf",
        accept_multiple_files=True
    )

    if uploaded_files:
        # 新規ファイルの追加
        new_files = [f for f in uploaded_files if f.name not in st.session_state.pdf_names]
        for file in new_files:
            temp_path = save_uploaded_file(file)
            if temp_path:
                st.session_state.pdf_files.append(temp_path)
                st.session_state.pdf_names.append(file.name)

    if st.session_state.pdf_files:
        st.write("**PDFファイルの並び替えと管理:**")
        
        # 修正点2: ドラッグ&ドロップでファイルの順序を変更
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
                try:
                    pdf_viewer(pdf_path, width=700)
                except Exception as e:
                    st.error(f"PDFの表示に失敗しました: {str(e)}")
            
            with col2:
                if st.button("削除", key=f"del_{i}"):
                    # ファイルをセッション状態から削除
                    st.session_state.pdf_files.pop(i)
                    st.session_state.pdf_names.pop(i)
                    st.rerun()

        # PDF結合処理
        if st.button("PDFを結合"):
            if len(st.session_state.pdf_files) > 0:
                progress_bar = st.progress(0)
                st.write("PDFを結合中...")
                
                merged_pdf_path = merge_pdfs(st.session_state.pdf_files, progress_bar)
                if merged_pdf_path:
                    st.success("PDF結合が完了しました！")
                    
                    with open(merged_pdf_path, "rb") as f:
                        st.download_button(
                            "結合したPDFをダウンロード",
                            f,
                            file_name="merged_pdf.pdf",
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