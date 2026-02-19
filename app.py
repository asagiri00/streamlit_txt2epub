import streamlit as st
import zipfile
import html
import io
import uuid
import os
import re
import chardet
from pathlib import Path
from charset_normalizer import from_bytes

# 페이지 설정
st.set_page_config(
    page_title="TXT2EPUB 변환기",
    page_icon="📚",
    layout="wide"
)

# CSS 스타일링 - 다크모드 대응
st.markdown("""
<style>
    /* 진행바 색상 */
    .stProgress > div > div > div > div {
        background-color: #4CAF50;
    }
    
    /* 업로드 텍스트 */
    .upload-text {
        font-size: 1.2em;
        color: #666;
    }
    
    /* 다크모드 대응 */
    @media (prefers-color-scheme: dark) {
        .upload-text {
            color: #aaa;
        }
    }
    
    /* 성공 메시지 박스 */
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    
    /* 다크모드 성공 메시지 */
    @media (prefers-color-scheme: dark) {
        .success-box {
            background-color: #1e3a2a;
            border-color: #2d6a4f;
            color: #a7f3d0;
        }
    }
    
    /* 파일 목록 컨테이너 */
    .file-list {
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #ddd;
        padding: 10px;
        border-radius: 5px;
        background-color: #ffffff;
    }
    
    /* 다크모드 파일 목록 */
    @media (prefers-color-scheme: dark) {
        .file-list {
            background-color: #1e1e1e;
            border-color: #444;
            color: #e0e0e0;
        }
    }
    
    /* 통계 카드 - 다크모드 대응 */
    .stat-card {
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        background-color: #f0f2f6;
        color: #31333F;
        border: 1px solid #e0e0e0;
    }
    
    /* 다크모드 통계 카드 */
    @media (prefers-color-scheme: dark) {
        .stat-card {
            background-color: #262730;
            color: #fafafa;
            border-color: #404040;
        }
        
        .stat-card h3, .stat-card h4, .stat-card p {
            color: #fafafa !important;
        }
    }
    
    /* 정보 메시지 박스 - 다크모드 대응 */
    .info-box {
        padding: 0.75rem;
        border-radius: 0.25rem;
        background-color: #e7f3ff;
        border: 1px solid #b8daff;
        color: #004085;
    }
    
    @media (prefers-color-scheme: dark) {
        .info-box {
            background-color: #1e3a5f;
            border-color: #2d5a8a;
            color: #b8daff;
        }
    }
    
    /* 경고 메시지 박스 - 다크모드 대응 */
    .warning-box {
        padding: 0.75rem;
        border-radius: 0.25rem;
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
    }
    
    @media (prefers-color-scheme: dark) {
        .warning-box {
            background-color: #3a3a1e;
            border-color: #5a5a2d;
            color: #ffd966;
        }
    }
    
    /* 파일 목록 텍스트 - 다크모드 대응 */
    .file-list-item {
        padding: 4px 0;
        border-bottom: 1px solid #f0f0f0;
    }
    
    @media (prefers-color-scheme: dark) {
        .file-list-item {
            border-bottom-color: #333;
        }
    }
    
    /* 다운로드 버튼 컨테이너 */
    .download-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 10px;
        margin-top: 20px;
    }
    
    /* 스트림릿 기본 컴포넌트 다크모드 대응 */
    @media (prefers-color-scheme: dark) {
        .stText, .stMarkdown, .stSubheader {
            color: #fafafa;
        }
        
        /* 사이드바 텍스트 색상 */
        .css-1d391kg, .css-163ttbj, .css-1v3fvcr {
            color: #fafafa;
        }
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# 상수 정의
# -------------------------
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB
MAX_TOTAL_SIZE = 1024 * 1024 * 1024  # 1GB
ALLOWED_IMAGE_TYPES = ["jpg", "jpeg", "png"]

# 폰트 설정
FONTS = {
    "나눔고딕": {
        "file": "NanumGothic.otf",
        "css_name": "NanumGothic",
        "family": "'NanumGothic', sans-serif"
    },
    "리디바탕": {
        "file": "RIDIBatang.otf",
        "css_name": "RIDIBatang",
        "family": "'RIDIBatang', serif"
    }
}

# -------------------------
# 인코딩 처리 함수
# -------------------------

def detect_encoding(file_content):
    """파일의 인코딩을 감지하고 UTF-8로 변환"""
    try:
        # charset-normalizer로 감지
        result = from_bytes(file_content).best()
        if result and result.encoding:
            detected_encoding = result.encoding
            text = str(result)
            return detected_encoding, text
        
        # chardet로 시도
        detected = chardet.detect(file_content)
        detected_encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
        text = file_content.decode(detected_encoding, errors='replace')
        return detected_encoding, text
        
    except Exception as e:
        # 모든 시도 실패시 기본 인코딩으로 시도
        for encoding in ['utf-8', 'cp949', 'euc-kr', 'latin-1', 'cp1252']:
            try:
                text = file_content.decode(encoding, errors='replace')
                return encoding, text
            except:
                continue
        
        # 최후의 수단
        return 'unknown', file_content.decode('utf-8', errors='replace')

# -------------------------
# 유틸리티 함수
# -------------------------

def format_size(size_bytes):
    """파일 크기를 읽기 쉬운 형식으로 변환"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    else:
        return f"{size_bytes/(1024*1024):.1f} MB"

def extract_metadata(filename):
    """파일명에서 제목과 저자 추출"""
    name = Path(filename).stem
    author = "미상"
    title = name
    
    # 패턴 1: 제목 - 저자
    if " - " in name:
        parts = name.split(" - ", 1)
        title, author = parts[0].strip(), parts[1].strip()
    # 패턴 2: 제목_저자
    elif "_" in name:
        parts = name.split("_", 1)
        title, author = parts[0].strip(), parts[1].strip()
    # 패턴 3: 제목(저자)
    elif "(" in name and name.endswith(")"):
        match = re.search(r"(.+)\((.+)\)", name)
        if match:
            title, author = match.group(1).strip(), match.group(2).strip()
    
    # 파일명에 사용할 수 없는 문자 제거
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    return title, author, safe_title

def detect_chapters(lines):
    """텍스트에서 챕터 자동 감지"""
    chapters = []
    current_chapter = "시작"
    current_lines = []
    chapter_pattern = re.compile(r'^(제\s?\d+\s?[화장편]|Chapter\s+\d+|\d+\.|제\s*\d+\s*장)')
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # 챕터 제목 감지
        if chapter_pattern.match(line_stripped):
            if current_lines:
                chapters.append((current_chapter, current_lines))
            current_chapter = line_stripped
            current_lines = []
        else:
            current_lines.append(html.escape(line_stripped))
    
    # 마지막 챕터 추가
    if current_lines:
        chapters.append((current_chapter, current_lines))
    
    return chapters if chapters else [("본문", [html.escape(l.strip()) for l in lines if l.strip()])]

def build_single_epub(file_name, file_content, cover_image=None, use_chapter_split=True, selected_font="나눔고딕"):
    """단일 TXT 파일을 EPUB으로 변환"""
    try:
        epub_stream = io.BytesIO()
        book_id = str(uuid.uuid4())
        
        # 메타데이터 추출
        title, author, safe_title = extract_metadata(file_name)
        
        # 인코딩 감지 및 UTF-8로 변환
        detected_encoding, text = detect_encoding(file_content)
        
        # 디버깅을 위한 인코딩 정보 (선택사항)
        if detected_encoding.lower() != 'utf-8':
            st.info(f"📄 '{file_name}' 인코딩: {detected_encoding} → UTF-8 변환됨")
        
        lines = text.splitlines()
        
        # 폰트 설정
        font_info = FONTS.get(selected_font, FONTS["나눔고딕"])
        font_file = font_info["file"]
        font_css_name = font_info["css_name"]
        font_family = font_info["family"]
        
        # 챕터 분할
        if use_chapter_split:
            chapters = detect_chapters(lines)
        else:
            chapters = [("본문", [html.escape(l.strip()) for l in lines if l.strip()])]
        
        # CSS 내용
        css_content = f'''
        @font-face {{
            font-family: '{font_css_name}';
            src: url('fonts/{font_file}');
        }}
        body {{ 
            font-family: {font_family};
            line-height: 1.8;
            margin: 5% 8%;
            text-align: justify;
            word-break: break-all;
        }}
        p {{
            margin-top: 0;
            margin-bottom: 1.5em;
            text-indent: 1em;
        }}
        h1, h2 {{
            text-align: center;
            font-weight: bold;
        }}
        h1 {{
            font-size: 1.8em;
            margin-bottom: 1em;
        }}
        h2 {{
            font-size: 1.4em;
            margin: 1.5em 0 1em 0;
        }}
        .author {{
            text-align: center;
            font-size: 1.2em;
            margin-bottom: 2em;
            color: #666;
        }}
        '''
        
        with zipfile.ZipFile(epub_stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # mimetype 파일 (압축하지 않음)
            zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            
            # container.xml
            container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>'''
            zf.writestr("META-INF/container.xml", container_xml)
            
            # 폰트 추가
            with open(font_file, "rb") as f:
                zf.writestr(f"OEBPS/fonts/{font_file}", f.read())
            
            # CSS 추가
            zf.writestr("OEBPS/style.css", css_content)
            
            # 표지 처리
            cover_manifest = ""
            cover_meta = ""
            cover_spine = ""
            
            if cover_image:
                # 표지 이미지 저장
                zf.writestr("OEBPS/cover.jpg", cover_image.getvalue())
                
                # 표지 XHTML
                cover_xhtml = '''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>표지</title>
    <style type="text/css">
        body { margin:0; padding:0; text-align:center; background:#f5f5f5; }
        img { max-width:100%; height:auto; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        .cover-container { padding:20px; }
    </style>
</head>
<body>
    <div class="cover-container">
        <img src="cover.jpg" alt="Cover" />
    </div>
</body>
</html>'''
                zf.writestr("OEBPS/cover.xhtml", cover_xhtml)
                
                cover_manifest = f'''
        <item id="cover-img" href="cover.jpg" media-type="image/jpeg"/>
        <item id="cover-xhtml" href="cover.xhtml" media-type="application/xhtml+xml"/>'''
                cover_meta = '<meta name="cover" content="cover-img"/>'
                cover_spine = '<itemref idref="cover-xhtml"/>'
            
            # 챕터 처리
            manifest_items = ""
            spine_items = cover_spine
            ncx_navpoints = ""
            
            for i, (ch_title, ch_lines) in enumerate(chapters):
                fname = f"chapter_{i:04d}.xhtml"
                
                # 첫 번째 챕터에만 전체 제목 표시
                header = ""
                if i == 0:
                    header = f"<h1>{html.escape(title)}</h1>"
                    if author != "미상":
                        header += f'<p class="author">{html.escape(author)}</p>'
                
                chapter_header = f"<h2>{html.escape(ch_title)}</h2>"
                chapter_content = "".join(f"<p>{line}</p>" for line in ch_lines)
                
                xhtml = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <link rel="stylesheet" type="text/css" href="style.css"/>
    <title>{html.escape(ch_title)}</title>
</head>
<body>
    {header}
    {chapter_header}
    {chapter_content}
</body>
</html>'''
                
                zf.writestr(f"OEBPS/{fname}", xhtml)
                
                # manifest 항목 추가
                manifest_items += f'\n        <item id="chap{i}" href="{fname}" media-type="application/xhtml+xml"/>'
                spine_items += f'\n        <itemref idref="chap{i}"/>'
                
                # NCX 항목 추가
                ncx_navpoints += f'''
        <navPoint id="nav{i}" playOrder="{i+1}">
            <navLabel>
                <text>{html.escape(ch_title)}</text>
            </navLabel>
            <content src="{fname}"/>
        </navPoint>'''
            
            # ncx 파일 (목차)
            ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
    </head>
    <docTitle>
        <text>{html.escape(title)}</text>
    </docTitle>
    <navMap>
        {ncx_navpoints}
    </navMap>
</ncx>'''
            zf.writestr("OEBPS/toc.ncx", ncx)
            
            # 폰트 manifest 항목
            font_item = f'\n        <item id="font" href="fonts/{font_file}" media-type="application/vnd.ms-opentype"/>'
            
            # content.opf
            opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="uid">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:title>{html.escape(title)}</dc:title>
        <dc:creator>{html.escape(author)}</dc:creator>
        <dc:language>ko</dc:language>
        <dc:identifier id="uid">{book_id}</dc:identifier>
        {cover_meta}
    </metadata>
    <manifest>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
        <item id="css" href="style.css" media-type="text/css"/>{cover_manifest}{manifest_items}{font_item}
    </manifest>
    <spine toc="ncx">
        {spine_items}
    </spine>
</package>'''
            zf.writestr("OEBPS/content.opf", opf)
        
        epub_stream.seek(0)
        return (safe_title, epub_stream)
        
    except Exception as e:
        st.error(f"'{file_name}' 변환 중 오류 발생: {str(e)}")
        return None

def convert_all_files(files_data, cover_image=None, use_chapter_split=True, selected_font="나눔고딕"):
    """여러 파일을 각각 EPUB으로 변환"""
    converted_files = []
    total_files = len(files_data)
    
    # 진행 상태 표시를 위한 컨테이너
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, (file_name, file_content) in enumerate(files_data):
        status_text.text(f"📖 변환 중: {file_name} ({idx + 1}/{total_files})")
        
        # 단일 파일 변환 (첫 번째 파일에만 표지 적용)
        current_cover = cover_image if idx == 0 and cover_image else None
        result = build_single_epub(file_name, file_content, current_cover, use_chapter_split, selected_font)
        
        if result:
            converted_files.append(result)
        
        progress_bar.progress((idx + 1) / total_files)
    
    status_text.text("✅ 모든 파일 변환 완료!")
    return converted_files

def reset_all_states():
    """모든 세션 상태 초기화 (페이지 새로고침 효과)"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # 필수 상태 다시 초기화
    st.session_state.converted_files = []
    st.session_state.uploaded_files = []
    st.session_state.cover_image = None
    st.session_state.conversion_complete = False
    st.session_state.page_loaded = True

# -------------------------
# 메인 UI
# -------------------------

# 세션 상태 초기화 (처음 로드 시)
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.converted_files = []
    st.session_state.uploaded_files = []
    st.session_state.cover_image = None
    st.session_state.conversion_complete = False

st.title("📚 TXT2EPUB 변환기")
st.markdown('<p class="upload-text">여러 TXT 파일을 각각 EPUB 전자책으로 변환합니다.</p>', unsafe_allow_html=True)

# 사이드바 - 설정 및 파일 정보
with st.sidebar:
    st.header("⚙️ 변환 설정")
    
    # 폰트 선택
    selected_font = st.selectbox(
        "폰트 선택",
        options=list(FONTS.keys()),
        index=0,
        help="EPUB에 포함할 폰트를 선택하세요."
    )
    
    st.divider()
    
    # 챕터 분할 설정
    use_chapter_split = st.checkbox("자동 챕터 분할 사용", value=True, 
                                    help="텍스트에서 챕터를 자동으로 감지하여 분할합니다.")
    
    st.divider()
    
    # 파일 정보 섹션
    st.header("📊 파일 정보")
    
    if st.session_state.uploaded_files:
        total_files = len(st.session_state.uploaded_files)
        total_size = sum(len(f.getvalue()) for f in st.session_state.uploaded_files)
        avg_size = total_size / total_files if total_files > 0 else 0
        
        # 통계 카드
        st.markdown(f"""
        <div class="stat-card">
            <h3>{total_files}</h3>
            <p>전체 파일 수</p>
            <h4>{format_size(total_size)}</h4>
            <p>전체 용량</p>
            <p>평균: {format_size(avg_size)}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 파일 목록
        with st.expander("📋 파일 목록"):
            for file in st.session_state.uploaded_files:
                file_size = len(file.getvalue())
                st.markdown(f'<div class="file-list-item">• {file.name} ({format_size(file_size)})</div>', unsafe_allow_html=True)
        
        # 모든 파일 지우기 버튼
        if st.button("🗑️ 모든 파일 지우기", use_container_width=True, type="primary"):
            reset_all_states()
            st.rerun()
            
    else:
        st.info("업로드된 파일이 없습니다.")

# 메인 영역
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📂 TXT 파일 업로드")
    
    # 파일 업로더
    uploader_key = f"file_uploader_{len(st.session_state.uploaded_files)}"
    uploaded_files = st.file_uploader(
        "TXT 파일을 드래그하거나 클릭하여 업로드하세요 (여러 파일 선택 가능)",
        type=["txt"],
        accept_multiple_files=True,
        key=uploader_key,
        help=f"파일당 최대 {format_size(MAX_FILE_SIZE)}까지 업로드 가능합니다."
    )
    
    # 파일 크기 검증 및 저장
    if uploaded_files:
        valid_files = []
        invalid_files = []
        total_size = 0
        
        for file in uploaded_files:
            file_size = len(file.getvalue())
            if file_size <= MAX_FILE_SIZE:
                valid_files.append(file)
                total_size += file_size
            else:
                invalid_files.append((file.name, file_size))
        
        # 전체 용량 검증
        if total_size > MAX_TOTAL_SIZE:
            st.error(f"❌ 전체 용량이 초과되었습니다. ({format_size(total_size)} / {format_size(MAX_TOTAL_SIZE)})")
            valid_files = []
        
        if invalid_files:
            for name, size in invalid_files:
                st.error(f"❌ {name}: 용량 초과 ({format_size(size)} / {format_size(MAX_FILE_SIZE)})")
        
        if valid_files:
            # 중복 제거 (파일명 기준)
            unique_files = []
            seen_names = set()
            for file in valid_files:
                if file.name not in seen_names:
                    unique_files.append(file)
                    seen_names.add(file.name)
            
            if len(unique_files) != len(valid_files):
                st.warning(f"⚠️ 중복된 파일명이 제거되었습니다. ({len(valid_files)} → {len(unique_files)})")
            
            # 새로 업로드된 파일이 있으면 상태 업데이트
            if len(unique_files) != len(st.session_state.uploaded_files):
                st.session_state.uploaded_files = unique_files
                st.session_state.conversion_complete = False
                st.rerun()

with col2:
    st.subheader("🖼️ 표지 설정")
    
    # 표지 이미지 업로드
    cover_image = st.file_uploader(
        "표지 이미지 업로드 (선택사항)",
        type=ALLOWED_IMAGE_TYPES,
        key=f"cover_uploader_{len(st.session_state.uploaded_files)}",
        help="JPG, JPEG, PNG 파일을 업로드하세요.\n첫 번째 EPUB에만 표지가 적용됩니다."
    )
    
    if cover_image:
        st.session_state.cover_image = cover_image
        st.image(cover_image, caption="표지 미리보기", use_container_width=True)
        
        if len(st.session_state.uploaded_files) > 1:
            st.info("ℹ️ 여러 파일 변환 시 첫 번째 EPUB에만 표지가 적용됩니다.")
    else:
        st.session_state.cover_image = None
        st.info("표지 없이 변환합니다.")

# 변환 버튼 및 실행
if st.session_state.uploaded_files:
    st.divider()
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        convert_button = st.button(
            "🔮 EPUB 변환 시작",
            type="primary",
            use_container_width=True,
            disabled=len(st.session_state.uploaded_files) == 0
        )
    
    if convert_button:
        with st.spinner("📚 EPUB 변환 중..."):
            # 파일 데이터 준비
            files_data = [(f.name, f.getvalue()) for f in st.session_state.uploaded_files]
            
            # 변환 실행
            converted = convert_all_files(
                files_data,
                st.session_state.cover_image,
                use_chapter_split,
                selected_font
            )
            
            if converted:
                st.session_state.converted_files = converted
                st.session_state.conversion_complete = True
                
                # 성공 메시지
                st.markdown(f'''
                <div class="success-box">
                    ✨ {len(converted)}개 파일 변환 완료!
                </div>
                ''', unsafe_allow_html=True)
                
                st.rerun()

# 변환 완료 후 다운로드 섹션
if st.session_state.get('conversion_complete', False) and st.session_state.converted_files:
    st.divider()
    
    st.subheader("📥 다운로드")
    
    # 다운로드 옵션
    download_option = st.radio(
        "다운로드 방식 선택",
        ["개별 파일 다운로드", "ZIP 파일로 한번에 다운로드"],
        horizontal=True
    )
    
    if download_option == "개별 파일 다운로드":
        # 각 파일별 다운로드 버튼
        cols = st.columns(3)
        for idx, (safe_title, epub_data) in enumerate(st.session_state.converted_files):
            with cols[idx % 3]:
                file_size = len(epub_data.getvalue())
                display_title = safe_title[:15] + "..." if len(safe_title) > 15 else safe_title
                st.download_button(
                    label=f"📕 {display_title}.epub ({format_size(file_size)})",
                    data=epub_data,
                    file_name=f"{safe_title}.epub",
                    mime="application/epub+zip",
                    use_container_width=True,
                    key=f"download_{idx}"
                )
    
    else:  # ZIP 파일 다운로드
        # ZIP 파일 생성
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for safe_title, epub_data in st.session_state.converted_files:
                zf.writestr(f"{safe_title}.epub", epub_data.getvalue())
        
        total_files = len(st.session_state.converted_files)
        total_size = zip_buffer.tell()
        
        st.info(f"📦 {total_files}개 파일이 ZIP으로 압축됩니다. (예상 크기: {format_size(total_size)})")
        
        st.download_button(
            label="📥 모든 파일 ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name="converted_epubs.zip",
            mime="application/zip",
            use_container_width=True
        )

# 진행 중인 작업 표시
if st.session_state.uploaded_files and not st.session_state.get('conversion_complete', False):
    st.info("👆 'EPUB 변환 시작' 버튼을 클릭하여 변환을 시작하세요.")

# 사용 방법 안내
with st.expander("📖 사용 방법 안내"):
    st.markdown("""
    ### 📚 TXT2EPUB 변환기 사용법
    
    1. **TXT 파일 업로드**
       - 파일을 드래그 앤 드롭하거나 클릭하여 선택
       - 여러 파일 동시 업로드 가능 (파일당 최대 200MB)
    
    2. **인코딩 자동 변환**
       - 모든 텍스트 파일이 자동으로 UTF-8로 변환됨
       - CP949, EUC-KR 등 다양한 인코딩 지원
    
    3. **폰트 선택**
       - 나눔고딕 또는 리디바탕 중 선택 가능
    
    4. **표지 설정** (선택사항)
       - 모든 EPUB에 동일한 표지 이미지 사용 가능
       - 여러 파일 변환 시 첫 번째 파일에만 표지 적용
       - JPG, JPEG, PNG 형식 지원
    
    5. **변환 설정**
       - 자동 챕터 분할: 텍스트에서 챕터를 자동으로 감지
       - 폰트 자동 포함
    
    6. **변환 및 다운로드**
       - 'EPUB 변환 시작' 버튼 클릭
       - 변환 완료 후 개별 파일 또는 ZIP으로 다운로드
    
    ### 📁 파일명 형식 (메타데이터 자동 추출)
    - `제목 - 저자.txt`
    - `제목_저자.txt`
    - `제목(저자).txt`
    
    위 형식으로 저장하면 제목과 저자가 자동으로 EPUB 메타데이터에 포함됩니다.
    
    ### ⚠️ 주의사항
    - 파일명에 특수문자(\\ / : * ? " < > |)는 자동으로 제거됨
    - 모든 텍스트 파일은 UTF-8로 자동 변환되어 처리됨
    """)

# 푸터
st.divider()
st.markdown(
    '<p style="text-align: center; color: #666;">📚 TXT2EPUB 변환기 | 해당 앱은 바이브 코딩으로 생성 되었으며 완전한 프리웨어 입니다. 어떠한 수정도 가능합니다</p>',
    unsafe_allow_html=True
)