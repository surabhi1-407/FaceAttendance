import os
import time
import sqlite3
import io 
import logging 
import cv2
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware


DATABASE_NAME = 'employees.db'
SERVER_CAPTURES_DIR = 'server_face_captures'
FACE_MODEL_NAME = 'buffalo_l' #insightfacemodel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="Face Registration API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

face_analyzer = None
try:
    logger.info(f"Initializing InsightFace model: {FACE_MODEL_NAME}...")
    face_analyzer = FaceAnalysis(name=FACE_MODEL_NAME, allowed_modules=['detection', 'recognition'])
    face_analyzer.prepare(ctx_id=0) 
    logger.info("InsightFace model initialized successfully.")
except Exception as e:
    logger.exception("FATAL: Failed to initialize InsightFace model.", exc_info=True)
    face_analyzer = None 

def create_database():
    """Creates the SQLite database and tables if they don't exist."""
    if not os.path.exists(SERVER_CAPTURES_DIR):
        logger.info(f"Creating server captures directory: {SERVER_CAPTURES_DIR}")
        os.makedirs(SERVER_CAPTURES_DIR)

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                face_image_path TEXT NOT NULL,
                embedding BLOB NOT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
        logger.info("Table 'employees' checked/created.")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT NOT NULL,
                attendance_date TEXT NOT NULL,
                in_time TEXT,
                out_time TEXT,
                FOREIGN KEY (emp_id) REFERENCES employees (emp_id) ON DELETE CASCADE ON UPDATE CASCADE
            )''')
        logger.info("Table 'attendance_log' checked/created.")

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attendance_date_emp
            ON attendance_log (attendance_date, emp_id);
        ''')
        logger.info("Index 'idx_attendance_date_emp' checked/created.")

        conn.commit()
        logger.info(f"Database '{DATABASE_NAME}' schemas checked/created successfully.")

    except sqlite3.Error as e:
        logger.error(f"Database creation/check error: {e}", exc_info=True)
        if conn: conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


create_database()

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        conn.row_factory = sqlite3.Row # Optional: Return rows as dict-like objects
        return conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")


@app.get("/")
async def read_root():
    return {"message": "Face Registration API is running."}


@app.post("/register")
async def register_user(
    request: Request, # Access request details if needed (e.g., client IP)
    name: str = Form(...),
    emp_id: str = Form(...),
    image: UploadFile = File(...)
):
    """
    Registers a new user with their name, employee ID, and face image.
    Generates face embedding and saves data to the database.
    """
    if not face_analyzer:
         logger.error("Registration attempt failed: InsightFace model not available.")
         raise HTTPException(status_code=503, detail="Face analysis service is not available.")

    logger.info(f"Received registration request for Emp ID: {emp_id}, Name: {name}")

    # 1. Read and Decode Image
    try:
        image_bytes = await image.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail="No image data received.")

        # Decode image using OpenCV directly from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img_cv2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_cv2 is None:
            logger.error(f"Failed to decode image for Emp ID: {emp_id}")
            raise HTTPException(status_code=400, detail="Could not decode image file. Ensure it's a valid image format (PNG, JPG, etc.).")
        logger.info(f"Image decoded successfully for Emp ID: {emp_id}")

    except Exception as e:
        logger.error(f"Error reading/decoding image for Emp ID {emp_id}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing uploaded image: {e}")

    # 2. Face Analysis (Detection & Embedding)
    embedding_bytes = None
    try:
        # Perform face detection and recognition
        faces = face_analyzer.get(img_cv2)

        if not faces:
            logger.warning(f"No face detected in image for Emp ID: {emp_id}")
            raise HTTPException(status_code=400, detail="No face detected in the uploaded image. Please capture a clear photo.")
        if len(faces) > 1:
            logger.warning(f"Multiple faces ({len(faces)}) detected for Emp ID: {emp_id}")
            raise HTTPException(status_code=400, detail=f"Multiple faces ({len(faces)}) detected. Please ensure only one face is clearly visible.")

        # Exactly one face found
        embedding = faces[0].normed_embedding # NumPy array
        embedding_bytes = embedding.tobytes() # Convert to bytes for BLOB storage
        logger.info(f"Embedding generated successfully for Emp ID: {emp_id} (Size: {len(embedding_bytes)} bytes).")

    except HTTPException as he:
        raise he # Re-raise specific HTTP exceptions
    except Exception as e:
        logger.error(f"Error generating embedding for Emp ID {emp_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate face embedding: {e}")


    # 3. Save Image to Server Filesystem
    timestamp = int(time.time())
    safe_emp_id = "".join(c if c.isalnum() else "_" for c in emp_id)
    server_image_filename = f"{safe_emp_id}_{timestamp}{os.path.splitext(image.filename)[1]}" # Keep original extension
    server_image_path = os.path.join(SERVER_CAPTURES_DIR, server_image_filename)

    try:
        with open(server_image_path, "wb") as f:
            f.write(image_bytes)
        logger.info(f"Saved captured image to server path: {server_image_path}")
    except IOError as e:
        logger.error(f"Failed to save image file to server path {server_image_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save image file on server: {e}")

    conn = None
    if embedding_bytes:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM employees WHERE emp_id = ?", (emp_id,))
            existing_user = cursor.fetchone()
            if existing_user:
                 logger.warning(f"Attempt to register duplicate Emp ID: {emp_id}")
                 # Clean up the saved image file if the user already exists
                 try: os.remove(server_image_path)
                 except OSError: pass
                 raise HTTPException(status_code=409, detail=f"Employee ID '{emp_id}' already exists.") # 409 Conflict

            cursor.execute(
                "INSERT INTO employees (emp_id, name, face_image_path, embedding) VALUES (?, ?, ?, ?)",
                (emp_id, name, server_image_path, sqlite3.Binary(embedding_bytes))
            )
            conn.commit()
            logger.info(f"User {name} (ID: {emp_id}) registered successfully in database.")

            return JSONResponse(
                status_code=200, # 200 OK is fine for successful creation here
                content={"message": f"User '{name}' (ID: {emp_id}) registered successfully!"}
            )

        except HTTPException as he:
            # Re-raise specific HTTP exceptions (like 409 Conflict)
            raise he
        except sqlite3.Error as e:
            logger.error(f"Database error during registration for Emp ID {emp_id}: {e}", exc_info=True)
            # Clean up the saved image file if DB insert fails
            try: os.remove(server_image_path)
            except OSError: pass
            raise HTTPException(status_code=500, detail=f"Database error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during database saving for Emp ID {emp_id}: {e}", exc_info=True)
            # Clean up the saved image file on generic error
            try: os.remove(server_image_path)
            except OSError: pass
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred during saving: {e}")
        finally:
            if conn:
                conn.close()
    else:
        # This case should be caught earlier, but as a fallback
        logger.error("Registration aborted: Embedding was not generated.")
        # Clean up the saved image file
        try: os.remove(server_image_path)
        except OSError: pass
        raise HTTPException(status_code=500, detail="Embedding could not be generated. Cannot save to database.")



import sqlite3
import numpy as np
import cv2
import io
import os
from datetime import datetime
import logging
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.responses import JSONResponse

RECOGNITION_THRESHOLD = 0.45 # Example value, requires tuning!

logger = logging.getLogger(__name__) # Get existing logger

# Cache known faces to avoid hitting DB on every request (simple example)
# For production, consider more robust caching or periodic refresh
known_faces_cache = {}
known_faces_last_load_time = 0
CACHE_TIMEOUT = 300 # Reload known faces every 5 minutes (300 seconds)

def load_known_faces_from_db(force_reload=False):
    """
    Loads or reloads known faces (ID, name, embedding) from the database.
    Uses a simple time-based cache.
    """
    global known_faces_cache, known_faces_last_load_time
    current_time = time.time()

    if not force_reload and known_faces_cache and (current_time - known_faces_last_load_time < CACHE_TIMEOUT):
        logger.info("Using cached known faces.")
        return known_faces_cache

    logger.info("Loading/Reloading known faces from database...")
    new_known_faces = {}
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT emp_id, name, embedding FROM employees WHERE embedding IS NOT NULL")
        rows = cursor.fetchall()

        count = 0
        for row in rows:
            emp_id = row['emp_id'] # Assumes row_factory = sqlite3.Row
            name = row['name']
            embedding_blob = row['embedding']
            if embedding_blob:
                try:
                    # Deserialize BLOB to numpy array (float32)
                    embedding = np.frombuffer(embedding_blob, dtype=np.float32)
                    # Basic validation of embedding shape if needed (e.g., 512 for buffalo models)
                    if embedding.shape == (512,): # Adjust size if using a different model
                        new_known_faces[emp_id] = {'name': name, 'embedding': embedding}
                        count += 1
                    else:
                         logger.warning(f"Skipping invalid embedding shape {embedding.shape} for emp_id {emp_id}")
                except Exception as e:
                    logger.error(f"Error deserializing embedding for emp_id {emp_id}: {e}")
            else:
                 logger.warning(f"Skipping null embedding for emp_id {emp_id}")

        known_faces_cache = new_known_faces
        known_faces_last_load_time = current_time
        logger.info(f"Loaded {count} known faces into cache.")
        if count == 0:
            logger.warning("No valid known faces found in the database.")
        return known_faces_cache

    except sqlite3.Error as e:
        logger.error(f"Database error loading known faces: {e}", exc_info=True)
        # Return potentially stale cache or empty dict on error? Decide strategy.
        # For now, return empty to signal failure.
        return {}
    except Exception as e:
         logger.error(f"Unexpected error loading known faces: {e}", exc_info=True)
         return {}
    finally:
        if conn:
            conn.close()


def recognize_face_from_embedding(captured_embedding):
    """Compares captured embedding against cached known faces."""
    known_faces = load_known_faces_from_db() # Use the cached loader

    if captured_embedding is None or not known_faces:
        logger.warning("Recognition skipped: No captured embedding or no known faces.")
        return None, None, -1 # emp_id, name, similarity

    best_match_id = None
    best_match_name = None
    highest_similarity = -1 # Cosine similarity ranges from -1 to 1

    for emp_id, data in known_faces.items():
        known_embedding = data['embedding']
        name = data['name']

        # Calculate cosine similarity (ensure vectors are numpy arrays)
        similarity = np.dot(captured_embedding, known_embedding)

        if similarity > highest_similarity:
            highest_similarity = similarity
            best_match_id = emp_id
            best_match_name = name

    logger.info(f"Recognition - Best match: {best_match_name} (ID: {best_match_id}), Similarity: {highest_similarity:.4f}")

    if highest_similarity >= RECOGNITION_THRESHOLD:
        return best_match_id, best_match_name, highest_similarity
    else:
        logger.info(f"Recognition failed: Highest similarity {highest_similarity:.4f} is below threshold {RECOGNITION_THRESHOLD}")
        return None, None, highest_similarity


def log_attendance_in_db(emp_id):
    """
    Logs check-in or check-out time for the recognized employee ID.
    Returns a status string: "check_in_success", "check_out_success",
    "already_checked_out", "db_error".
    """
    today_date = datetime.now().strftime('%Y-%m-%d')
    current_time = datetime.now().strftime('%H:%M:%S')
    status = "db_error"  # Default status
    conn = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT log_id, in_time, out_time
            FROM attendance_log
            WHERE emp_id = ? AND attendance_date = ?
            ORDER BY log_id DESC LIMIT 1
        """, (emp_id, today_date))
        record = cursor.fetchone() 

        if record is None:
            logger.info(f"DB Log: Recording Check-in for emp_id {emp_id} at {current_time}")
            cursor.execute("""
                INSERT INTO attendance_log (emp_id, attendance_date, in_time)
                VALUES (?, ?, ?)
            """, (emp_id, today_date, current_time))
            status = "check_in_success"
        else:
            log_id = record['log_id']
            in_time = record['in_time']
            out_time = record['out_time']

            if in_time and not out_time:
                # Checked in but not checked out — perform check-out
                logger.info(f"DB Log: Recording Check-out for emp_id {emp_id} at {current_time} (Log ID: {log_id})")
                cursor.execute("""
                    UPDATE attendance_log SET out_time = ? WHERE log_id = ?
                """, (current_time, log_id))
                status = "check_out_success"
            elif in_time and out_time:
                logger.info(f"DB Log: Recording NEW Check-in for emp_id {emp_id} at {current_time} (already checked out once)")
                cursor.execute("""
                   INSERT INTO attendance_log (emp_id, attendance_date, in_time)
                   VALUES (?, ?, ?)
                """, (emp_id, today_date, current_time))
                status = "check_in_success"
            else:
                logger.warning(f"DB Log: Inconsistent record found for emp_id {emp_id} on {today_date} (log_id {log_id}). Recording new check-in.")
                cursor.execute("""
                   INSERT INTO attendance_log (emp_id, attendance_date, in_time)
                   VALUES (?, ?, ?)
                """, (emp_id, today_date, current_time))
                status = "check_in_success"


        conn.commit()
        logger.info(f"DB Log: Attendance log status for {emp_id}: {status}")

    except sqlite3.Error as e:
        logger.error(f"Database error recording attendance for emp_id {emp_id}: {e}", exc_info=True)
        status = "db_error" # Ensure status reflects DB error
        if conn: conn.rollback() # Rollback transaction on error
    except Exception as e:
        logger.error(f"Unexpected error recording attendance: {e}", exc_info=True)
        status = "error" # General error
        if conn: conn.rollback()
    finally:
        if conn:
            conn.close()

    return status


def create_database():
    """Creates the SQLite database and tables if they don't exist."""
    if not os.path.exists(SERVER_CAPTURES_DIR): # Assuming SERVER_CAPTURES_DIR is defined
        logger.info(f"Creating server captures directory: {SERVER_CAPTURES_DIR}")
        os.makedirs(SERVER_CAPTURES_DIR)

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                face_image_path TEXT NOT NULL, -- Path ON THE SERVER
                embedding BLOB NOT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
        logger.info("Table 'employees' checked/created.")

        # Attendance Log table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance_log (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_id TEXT NOT NULL,
                attendance_date TEXT NOT NULL, -- Format YYYY-MM-DD
                in_time TEXT,                 -- Format HH:MM:SS
                out_time TEXT,                -- Format HH:MM:SS
                FOREIGN KEY (emp_id) REFERENCES employees (emp_id) ON DELETE CASCADE ON UPDATE CASCADE
            )''')
        logger.info("Table 'attendance_log' checked/created.")

        # Index for faster attendance lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_attendance_date_emp ON attendance_log (attendance_date, emp_id);")
        logger.info("Index 'idx_attendance_date_emp' checked/created.")

        conn.commit()
        logger.info(f"Database '{DATABASE_NAME}' schemas checked/created successfully.")

    except sqlite3.Error as e:
        logger.error(f"Database creation/check error: {e}", exc_info=True)
        if conn: conn.rollback()
        raise # Re-raise to signal startup failure
    finally:
        if conn:
            conn.close()

@app.post("/recognize_attendance")
async def recognize_attendance(image: UploadFile = File(...)):
    """
    Receives an image, recognizes the face, and logs attendance.
    """
    if not face_analyzer:
         logger.error("Attendance check failed: InsightFace model not available.")
         raise HTTPException(status_code=503, detail="Face analysis service is not available.")

    # 1. Read and Decode Image
    try:
        image_bytes = await image.read()
        if not image_bytes:
            logger.warning("Attendance check: No image data received.")
            raise HTTPException(status_code=400, detail="No image data received.")

        nparr = np.frombuffer(image_bytes, np.uint8)
        img_cv2 = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img_cv2 is None:
            logger.error("Attendance check: Failed to decode image.")
            raise HTTPException(status_code=400, detail="Could not decode image file.")
        logger.info("Attendance check: Image decoded successfully.")

    except Exception as e:
        logger.error(f"Error reading/decoding image for attendance: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error processing uploaded image: {e}")

    # 2. Face Analysis
    captured_embedding = None
    try:
        faces = face_analyzer.get(img_cv2)

        if not faces:
            logger.info("Attendance check: No face detected.")
            # Return specific status for no face
            return JSONResponse(status_code=200, content={"status": "no_face"})
        if len(faces) > 1:
            logger.info(f"Attendance check: Multiple faces ({len(faces)}) detected.")
             # Return specific status for multiple faces
            return JSONResponse(status_code=200, content={"status": "multiple_faces"})

        captured_embedding = faces[0].normed_embedding
        logger.info("Attendance check: Embedding generated.")

    except Exception as e:
        logger.error(f"Error during face analysis for attendance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed during face analysis: {e}")

    # 3. Recognition
    emp_id, name, similarity = recognize_face_from_embedding(captured_embedding)

    if not emp_id:
        logger.info("Attendance check: Face not recognized (below threshold or no match).")
        # Return specific status for not recognized
        return JSONResponse(status_code=200, content={"status": "not_recognized", "similarity": float(similarity)}) # Send similarity back

    logger.info(f"Attendance check: Recognized as {name} (ID: {emp_id}) with similarity {similarity:.4f}")

    # 4. Log Attendance
    log_status = log_attendance_in_db(emp_id)

    if log_status in ["check_in_success", "check_out_success", "already_checked_out", "already_checked_in"]:
        # Return success status along with name/ID
        return JSONResponse(
            status_code=200,
            content={"status": log_status, "name": name, "emp_id": emp_id}
        )
    else: # db_error or other error from logging function
        logger.error(f"Attendance check: Failed to log attendance for {name} (ID: {emp_id}). Log status: {log_status}")
        raise HTTPException(status_code=500, detail=f"Failed to log attendance due to database or internal error.")


logger = logging.getLogger(__name__) # Get existing logger

@app.get("/attendance_log")
async def get_attendance_log():
    """
    Fetches the complete attendance log, joining with employee names.
    Returns data sorted newest first.
    """
    logger.info("Received request for /attendance_log")
    conn = None
    try:
        conn = get_db_connection() 
        cursor = conn.cursor()

        # Join attendance_log (a) with employees (e) to get names
        query = """
            SELECT a.emp_id, e.name, a.attendance_date, a.in_time, a.out_time
            FROM attendance_log a
            JOIN employees e ON a.emp_id = e.emp_id
            ORDER BY a.attendance_date DESC, a.log_id DESC
        """
        cursor.execute(query)
        records = cursor.fetchall() 
        result_list = [dict(record) for record in records]

        logger.info(f"Successfully fetched {len(result_list)} attendance records.")
        return JSONResponse(content=result_list)

    except sqlite3.Error as e:
        logger.error(f"Database error fetching attendance log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error fetching attendance log: {e}")
    except Exception as e:
         logger.error(f"Unexpected error fetching attendance log: {e}", exc_info=True)
         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()

