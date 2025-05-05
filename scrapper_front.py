import requests
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import logging
import json

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

scraper_url = st.secrets["api_endpoints"]["scraper_url"]
ocr_url = st.secrets["api_endpoints"]["ocr_url"]


# Configura página
st.set_page_config(page_title="Red Petroil | Facebook Post Monitor", page_icon="images/petroil_logo_gota.jpg",layout="wide")

# ==== 🎨 ESTILO PERSONALIZADO CSS ====
st.markdown("""
    <style>
    body {
        background-color: #ffffff;
    }
    .main {
        background-color: #000000;
    }
    header {
        background-color: #003366;
    }
    h1 {
        color: #003366;
    }
            
    .stButton > button {
        background-color: #003366;
        color: #ffffff;
        font-weight: bold;
        font-size: 16px;
        border: none;
        border-radius: 8px;
        padding: 0.6em 1.4em;
        height:auto;
        padding:2px;
        padding-left:5px;
        padding-right:5px;        
        box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease-in-out;
    }
            
    .stButton > button:hover {
        background-color: #FFD700;
        color: #003366;
        box-shadow: 2px 2px 15px rgba(0, 0, 0, 0.3);
        transform: scale(1.02);
        cursor: pointer;
    }
    .stButton >
    </style>
""", unsafe_allow_html=True)

# ==== 🛠️ Autenticación con Google Sheets ====
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

#creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPE)
# Below code is for hosting in streamlit code as it uses a project.toml secret handler
creds = Credentials.from_service_account_info(st.secrets["google"], scopes=SCOPE)
gc = gspread.authorize(creds)

_,centered_header,_=st.columns([3,4,3])

with centered_header:
    # ==== 🧢 Cabecera ====
    st.image("https://irp-cdn.multiscreensite.com/db564452/DESKTOP/jpg/780.jpg", width=250, use_container_width=False)
    st.title("Monitor de Publicaciones")
    st.markdown("**Red Petroil - Inteligencia de Marketing Digital**")
    st.markdown("---")

# ==== 📩 Entradas ====    
_,centered_fields,_=st.columns([2,4,2])
with centered_fields:
    _,c1,c2,c3,_=st.columns([1,3,3,3,1])
    with c1:    
        post_id = st.text_input("🔵 ID del Post")        
    with c2:
        sheet_name = st.text_input("📗 Proyecto Excel")
    with c3: 
        worksheet_name = st.text_input("📋 Hoja de Trabajo")

# Inicializa session_state
if "scraper_ready" not in st.session_state:
    st.session_state.scraper_ready = False
if "df_data" not in st.session_state:
    st.session_state.df_data = None

# Create a row with two buttons
_,col_scrape, col_display,col_ocr,_ = st.columns([3.5,1.5,1.5,1.5,3.5])

# Button to initiate scraping
with col_scrape:
    if st.button("🔄 Ejecutar Scraper"):
        if post_id and sheet_name and worksheet_name:
            st.session_state.post_id=post_id 
            with st.spinner("⛽ Ejecutando el scraper..."):
                try:
                    # Prepare the request data for your FastAPI endpoint
                    api_url = scraper_url                  
                    
                    # Create the request payload matching your ScrapRequest model
                    payload = {
                        "post_id": post_id,
                        "sheet_name": sheet_name,
                        "worksheet_name": worksheet_name
                    }
                    
                    # Make a POST request to the API
                    response = requests.post(api_url, json=payload, timeout=180)
                    
                    if response.status_code == 200:
                        response_data = response.json()
                        st.success(response_data.get("response", ""))    
                        
                        # After successful scraping, automatically load the data
                        if "Success" in response_data.get("response"):
                            try:
                                sh = gc.open(sheet_name)
                                worksheet = sh.worksheet(worksheet_name)
                                
                                data = worksheet.get_all_records()
                                for row in data:
                                    row['user_id'] = str(row['user_id'])
                                df = pd.DataFrame(data)
                            
                                st.session_state.scraper_ready = True
                                st.session_state.df_data = df                            
                            except Exception as e:
                                import traceback
                                st.error(f"❌ Error: {e}")
                                print("🔴 Exception:", e, flush=True)
                                traceback.print_exc()
                                st.warning(f"✅ Scraper ejecutado, pero no se pudo cargar los datos: {e}")
                    else:
                        st.error(f"❌ Error del API: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"❌ Error al conectar con el scraper: {e}")
        else:
            st.warning("🔴 Por favor, completa la información de los campos.")

# Button to display data from Google Sheets
with col_display:
    if st.button("📊 Mostrar Datos"):
        if sheet_name and worksheet_name:
            st.session_state.post_id=post_id   
            with st.spinner("⛽ Cargando comentarios del post..."):
                try:                   
                    sh = gc.open(sheet_name)
                    worksheet = sh.worksheet(worksheet_name)
                    data = worksheet.get_all_records()
                    for row in data:
                        row['user_id'] = str(row['user_id'])
                    df = pd.DataFrame(data)                
                    # Guarda en session_state
                    st.session_state.scraper_ready = True
                    st.session_state.df_data = df
                    st.success("✅ Comentarios cargados correctamente")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
        else:
            st.warning("🔴 Por favor, completa la información de los campos.")

# OCR Service
required_fields = ["date", "address", "station", "total", "quantity"]
default_fields = {"date":"None","address":"None","station":"None","total":0,"quantity":0}
error_placeholder = st.empty()  # Create a placeholder for errors

with col_ocr:
    if st.button("🔄 Ejecutar OCR"):
        error_placeholder.empty() 
        if post_id and sheet_name and worksheet_name:
            st.session_state.post_id=post_id 
            sh = gc.open(sheet_name)        
            worksheet = sh.worksheet(worksheet_name)
            headers=worksheet.row_values(1)
            records = worksheet.get_all_records()
            image_rows = [
                (i + 2, row) for i, row in enumerate(records)
                if row.get("has_attachment")
                and row["has_attachment"].strip().lower() != "no"
                and (row.get("total") is None or row.get("total") == "" or str(row.get("total")).strip() == "")  # solo incluye registros donde total está vacío
                ]
            if not image_rows:
                st.info("No image attachments found in the sheet.")
            else:
                updated = False
                for field in required_fields:
                    if field not in headers:
                        headers.append(field)
                        updated = True

                if updated:
                    worksheet.update('A1', [headers])
                
                headers = worksheet.row_values(1)  # Refresh headers

                progress_bar = st.progress(0)
                total_images = len(image_rows)
                for i,(row_index,row) in enumerate(image_rows):
                    
                    error_placeholder.empty() 
                    image_url = row["has_attachment"]                    
                    with st.container():
                        per_image_error = st.empty()                                       
                        try:
                            # Call OCR API
                            resp = requests.post(ocr_url, json={"image_url": image_url},timeout=20)
                            #resp.raise_for_status()
                            structured = resp.json().get("structured_text", {})                       
                            print(structured)
                            # Update sheet
                            for key in required_fields:
                                if key in structured and key in headers:
                                    col_index = headers.index(key) + 1
                                    worksheet.update_cell(row_index, col_index, str(structured[key])) 
                                      
                        except Exception as e:
                            per_image_error.error(f"❌ Error processing image: {e}")
                            for key in required_fields:
                                if key in default_fields and key in headers:
                                    col_index = headers.index(key) + 1
                                    worksheet.update_cell(row_index, col_index, str(default_fields[key]))
                            
                    progress_bar.progress((i + 1) / total_images)
                st.success(f"✅ Proceso de OCR completado.")
        else:
            st.warning("🔴 Por favor, completa la información solicitada de los campos arriba.")

# ==== Mostrar datos si ya se ejecutó el scraper ====
if st.session_state.scraper_ready and st.session_state.df_data is not None:    
    # Creamos dos columnas: una para el DataFrame y otra para la imagen
    col1, col2 = st.columns([5, 5])
    with col1:
        st.subheader("📊 Comentarios del Post")
        filter_button= st.checkbox("Comentarios con Imagenes")
        if filter_button:
            df = st.session_state.df_data
            df = df[df['has_attachment'].str.lower()!='no']
        else:
            df = st.session_state.df_data    
        event = st.dataframe(
            df.astype(str),
            column_config={
                "has_attachment": st.column_config.LinkColumn(
                    "Imagen Asociada",
                    help="Imagen Asociada al comentario",
                    validate=r"^https://[a-z]+\.streamlit\.app$",
                    max_chars=100,
                    display_text=r"https://(.*?)\.streamlit\.app"
                ),                
            },
            use_container_width=True,
            hide_index=False,
            on_select="rerun",
            selection_mode="single-row",
        )
        comment = event.selection.rows
        if st.session_state and len(comment) == 1:
             row = df.iloc[comment[0]]
             comment_url= f"https://www.facebook.com/{post_id}?comment_id={row.get("comment_id")}"
             st.markdown(f"🔗 [Abrir Comentario]({comment_url})", unsafe_allow_html=True)        
                        
    with col2:
        st.markdown("### Imagen del Post")
        comment = event.selection.rows
        if len(comment) == 1:
            row = df.iloc[comment[0]]
            attachment = row.get("has_attachment", "No")        
            if isinstance(attachment, str) and attachment.strip().lower() != "no":  
                # Contenedor con clase personalizada
                st.markdown('<div class="custom-image-container">', unsafe_allow_html=True)
                st.image(attachment.strip(), width=300)
                st.markdown('</div>', unsafe_allow_html=True)

    # Link a Google Sheets
    sheet_id = gc.open(sheet_name).id
    sheet_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?usp=sharing"
    st.markdown(f"🔗 [Abrir en Google Sheets]({sheet_url})", unsafe_allow_html=True)