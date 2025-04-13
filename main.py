from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.camera import Camera
from kivy.uix.image import Image
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
from kivy.metrics import dp
from kivy.properties import NumericProperty, ObjectProperty
from kivy.clock import Clock
from datetime import datetime
from kivy.clock import Clock # <<< ADDED (Optional: for potential threading updates)
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
import os
import time
import requests # For making API calls
import threading # To run network calls without blocking UI
from PIL import Image as PILImage # Still needed for potential preview handling if needed, but not conversion
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.logger import Logger # Use Kivy's logger
from kivy.utils import platform


from kivy.utils import platform

if platform == 'android':
    try:
        from android.permissions import request_permissions, Permission
    except ImportError:
        print("Warning: android.permissions module not available outside Android.")

ADMIN_PASSWORD = "oye" 
BACKEND_URL = "http://192.168.29.31:8000"
REGISTER_ENDPOINT = f"{BACKEND_URL}/register"
RECOGNIZE_ENDPOINT = f"{BACKEND_URL}/recognize_attendance"
ATTENDANCE_LOG_ENDPOINT = f"{BACKEND_URL}/attendance_log"


class ResponsiveButton(Button):
    min_height = NumericProperty(dp(60))
    
    def __init__(self, **kwargs):
        super(ResponsiveButton, self).__init__(**kwargs)
        self.bind(size=self.update_text_size)
    
    def update_text_size(self, instance, size):
        # Adjust font size based on button dimensions
        width_factor = self.width * 0.03
        height_factor = self.height * 0.4
        self.font_size = min(width_factor, height_factor)
        
        # Set text size to button width for proper wrapping
        self.text_size = (self.width * 0.9, None)

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(
            orientation='vertical',
            padding=[Window.width * 0.05, Window.height * 0.05],
            spacing=Window.height * 0.03
        )
        
        # Create responsive buttons with meaningful labels
        self.button1 = ResponsiveButton(
            text='Mark Attendance',
            background_color=get_color_from_hex('#4CAF50'),
            min_height=dp(60),
            halign='center',
            valign='middle'
        )
        
        self.button2 = ResponsiveButton(
            text='Register User',
            background_color=get_color_from_hex('#2196F3'),
            min_height=dp(60),
            halign='center',
            valign='middle',
            on_press=self.open_register_screen
        )
        
        self.button3 = ResponsiveButton(
            text='Admin Panel',
            background_color=get_color_from_hex('#FF9800'),
            min_height=dp(60),
            halign='center',
            valign='middle'
        )
        
        self.button1.bind(on_press=self.open_attendance_screen)
        self.button3.bind(on_press=self.show_admin_login_popup)
        #layout.add_widget(self.button3)

        # Add buttons to the layout
        self.layout.add_widget(self.button1)
        self.layout.add_widget(self.button2)
        self.layout.add_widget(self.button3)
        
        # Bind to window size changes to update padding
        Window.bind(size=self.update_layout_padding)
        
        self.add_widget(self.layout)
    
    def update_layout_padding(self, instance, size):
        # Update padding when window size changes
        self.layout.padding = [size[0] * 0.05, size[1] * 0.05]
        self.layout.spacing = size[1] * 0.03
        
    def open_register_screen(self, instance):
        self.manager.current = 'register'

    def open_attendance_screen(self, instance):
        self.manager.current = 'attendance'


    def show_admin_login_popup(self, instance):
        """Creates and displays the password entry popup."""
        popup_content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        password_input = TextInput(
            password=True,
            multiline=False,
            size_hint_y=None,
            height=dp(40),
            hint_text="Enter Admin Password"
        )
        submit_button = Button(text='Submit', size_hint_y=None, height=dp(40))
        cancel_button = Button(text='Cancel', size_hint_y=None, height=dp(40))
        self.error_label = Label(text='', color=(1, 0, 0, 1), size_hint_y=None, height=dp(30)) # For error messages

        popup_content.add_widget(Label(text='Admin Access Required'))
        popup_content.add_widget(password_input)
        popup_content.add_widget(self.error_label) # Add error label
        button_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(5))
        button_layout.add_widget(cancel_button)
        button_layout.add_widget(submit_button)
        popup_content.add_widget(button_layout)

        popup = Popup(
            title='Admin Login',
            content=popup_content,
            size_hint=(0.7, 0.5),
            auto_dismiss=False
        )

        # Bind actions
        submit_button.bind(on_press=lambda *args: self.check_admin_password(password_input.text, popup))
        cancel_button.bind(on_press=popup.dismiss)

        popup.open()

    def check_admin_password(self, entered_password, popup):
        """Verifies the password and navigates if correct."""
        if entered_password == ADMIN_PASSWORD:
            print("Admin access granted.")
            popup.dismiss()
            # Navigate to the AdminScreen (make sure 'admin_records' matches the name in ScreenManager)
            self.manager.current = 'admin_records'
        else:
            print("Admin access denied: Incorrect password.")
            # Show error message inside the popup instead of dismissing
            self.error_label.text = "Incorrect Password!"


class AttendanceScreen(Screen):
    def __init__(self, **kwargs):
        super(AttendanceScreen, self).__init__(**kwargs)
        # No InsightFace or DB interactions here
        self.temp_image_path = None # Path for temporary capture

        # --- Build UI ---
        # Using main_layout consistently with RegisterScreen
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        title_label = Label(
            text='Point Camera at Face for Attendance',
            font_size=dp(24),
            size_hint_y=None,
            height=dp(50)
        )
        main_layout.add_widget(title_label)

        # Use a container for the camera
        camera_container = BoxLayout(size_hint_y=1) # Let it take available vertical space

        # Initialize Camera
        try:

            self.camera = Camera(resolution=(640, 480), play=False, index=1)
            self.camera.rotation = -90  # or try -90 depending on your device

        except Exception as e:
            Logger.error(f"AttendanceScreen: Failed to initialize camera: {e}")
            self.camera = None # Flag that camera is unavailable
            # Optionally show a persistent error or disable functionality

        if self.camera:
            camera_container.add_widget(self.camera)
        else:
            # Show placeholder if camera failed
            camera_container.add_widget(Label(text="Camera not available", color=(1,0,0,1)))

        main_layout.add_widget(camera_container)

        # Capture/Attendance Button
        self.capture_button = Button(
            text='Mark Attendance (Check-in / Check-out)',
            size_hint_y=None, height=dp(60),
            background_color=get_color_from_hex('#4CAF50'),
            disabled=(self.camera is None) # Disable if camera failed
        )
        self.capture_button.bind(on_press=self.trigger_attendance_check)
        main_layout.add_widget(self.capture_button)

        # Status Label
        self.result_label = Label(
            text='Status: Ready',
            font_size=dp(18),
            size_hint_y=None,
            height=dp(40)
        )
        main_layout.add_widget(self.result_label)

        # Back Button
        self.back_button = Button(
            text='Back to Main',
            size_hint_y=None,
            height=dp(50),
            background_color=get_color_from_hex('#9E9E9E')
        )
        self.back_button.bind(on_press=self.go_back)
        main_layout.add_widget(self.back_button)

        self.add_widget(main_layout)
        # No database table creation here

    def on_enter(self, *args):
        self.result_label.text = 'Status: Ready'
        self.temp_image_path = None  # Reset temp path

        if self.camera:
            Logger.info("AttendanceScreen: Scheduling delayed camera start.")
            Clock.schedule_once(lambda dt: self.start_camera_safely(), 0.5)
        else:
            self.result_label.text = "Status: Camera unavailable"
            self.capture_button.disabled = True
            Logger.warning("AttendanceScreen: Camera is None.")
            self.show_popup("Camera Error", "Camera device could not be initialized.")

        def on_leave(self, *args):
            """Called when the screen is left."""
            if hasattr(self, 'camera') and self.camera and self.camera.play:
                self.camera.play = False
                Logger.info("AttendanceScreen: Camera stopped.")
            # Clean up any lingering popups or state if needed
            self.dismiss_popup_if_exists()

    def start_camera_safely(self):
        try:
            self.camera.rotation = -90  # Rotate for portrait orientation
            self.camera.play = True
            Logger.info("AttendanceScreen: Camera started with delay.")
            self.capture_button.disabled = False
        except Exception as e:
            Logger.error(f"AttendanceScreen: Error starting camera with delay: {e}")
            self.result_label.text = f"Error starting camera: {e}"
            if self.camera:
                self.camera.play = False
            self.capture_button.disabled = True
            self.show_popup("Camera Error", f"Could not start camera: {e}")


    def trigger_attendance_check(self, instance):
        """Captures image and starts the backend check thread."""
        if not self.camera or not self.camera.play:
            self.result_label.text = "Error: Camera not active."
            Logger.warning("Attendance: Capture failed, camera not playing.")
            return

        # Disable button, show processing message
        instance.disabled = True
        self.result_label.text = "Processing..."

        try:
            # Use app's user_data_dir for temporary storage
            app = App.get_running_app()
            temp_dir = os.path.join(app.user_data_dir, 'temp_attendance')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            timestamp = int(time.time())
            self.temp_image_path = os.path.join(temp_dir, f"attendance_{timestamp}.png")

            Logger.info(f"Attendance: Capturing temporary image to: {self.temp_image_path}")
            self.camera.export_to_png(self.temp_image_path)
            Logger.info(f"Attendance: Successfully saved temporary PNG.")

            # Start the background thread for API call
            threading.Thread(target=self.attendance_check_thread, args=(self.temp_image_path,)).start()

        except Exception as e:
            Logger.error(f"Attendance: Error during photo capture: {e}", exc_info=True)
            self.result_label.text = f"Error capturing photo: {e}"
            self.show_popup("Capture Error", f"Failed to capture photo: {e}")
            instance.disabled = False # Re-enable button on capture error
            self.temp_image_path = None # Reset path


    def attendance_check_thread(self, image_path):
        """Sends captured image to backend for recognition and logging (runs in thread)."""
        files = None
        response_data = {"status": "error", "detail": "Unknown error"} # Default error response

        try:
            if not os.path.exists(image_path):
                 raise FileNotFoundError(f"Temporary image file not found at {image_path}")

            files = {'image': (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')}

            Logger.info(f"Attendance: Sending request to {RECOGNIZE_ENDPOINT}")
            response = requests.post(RECOGNIZE_ENDPOINT, files=files, timeout=30) # Timeout
            response.raise_for_status() # Raise HTTPError for 4xx/5xx

            # Process successful response (usually 200 OK)
            response_data = response.json() # Get JSON response from backend
            Logger.info(f"Attendance: Received response: {response_data}")

        except FileNotFoundError as e:
             Logger.error(f"Attendance: File error: {e}")
             response_data = {"status": "error", "detail": str(e)}
        except requests.exceptions.ConnectionError as e:
             Logger.error(f"Attendance: Connection error: {e}")
             response_data = {"status": "error", "detail": f"Connection Error: Could not connect to the server at {BACKEND_URL}. Ensure it's running and the IP is correct."}
        except requests.exceptions.Timeout:
             Logger.error(f"Attendance: Request timed out")
             response_data = {"status": "error", "detail": "Connection Error: The request timed out. The server might be busy or unreachable."}
        except requests.exceptions.HTTPError as e:
            error_msg = f"Server error (HTTP {response.status_code})"
            try:
                # Try to get detail from FastAPI response
                detail = response.json().get("detail", response.text) # Use raw text as fallback
                error_msg += f": {detail}"
                # Store the detail for display
                response_data = response.json() if response.headers.get('content-type') == 'application/json' else {"status": "error", "detail": detail}
                if "status" not in response_data: response_data["status"] = "error" # Ensure status key exists
            except Exception:
                 response_data = {"status": "error", "detail": error_msg + f": {response.text}"}
            Logger.error(f"Attendance: HTTP error: {error_msg}")
        except Exception as e:
            Logger.error(f"Attendance: Unexpected error during check: {e}", exc_info=True)
            response_data = {"status": "error", "detail": f"An unexpected client error occurred: {e}"}
        finally:
            # Ensure the file handle is closed
            if files and 'image' in files and files['image']:
                try:
                    files['image'][1].close()
                except Exception as e:
                    Logger.error(f"Attendance: Error closing image file handle: {e}")

            # Clean up the temporary image file
            try:
                 if os.path.exists(image_path):
                     os.remove(image_path)
                     Logger.info(f"Attendance: Cleaned up temporary file: {image_path}")
            except Exception as e:
                 Logger.error(f"Attendance: Failed to clean up temp file {image_path}: {e}")

            # Schedule UI update on the main Kivy thread
            Clock.schedule_once(lambda dt: self.handle_attendance_response(response_data))


    def handle_attendance_response(self, response_data):
        """Updates the UI based on the backend response (called via Clock)."""
        status = response_data.get("status", "error")
        name = response_data.get("name", "") # Get name if available
        detail = response_data.get("detail", "An unknown error occurred.")

        message = f"Status: {status}" # Default message

        if status == "check_in_success":
            message = f"Welcome, {name}! Check-in recorded."
            self.show_popup("Attendance Success", message)
        elif status == "check_out_success":
            message = f"Goodbye, {name}! Check-out recorded."
            self.show_popup("Attendance Success", message)
        elif status == "already_checked_out":
             message = f"Status: {name}, you already checked out today."
             self.show_popup("Attendance Info", message)
        elif status == "already_checked_in": # Assuming backend might send this
             message = f"Status: {name}, you are already checked in."
             self.show_popup("Attendance Info", message)
        elif status == "not_recognized":
            message = "Status: Face not recognized. Please try again."
            self.show_popup("Attendance Failed", "Face not recognized.")
        elif status == "error":
            message = f"Error: {detail}"
            self.show_popup("Attendance Error", message) # Show detailed error in popup
            message = "Status: Error occurred" # Keep label shorter
        elif status == "no_face":
            message = "Status: No face detected. Try again."
            self.show_popup("Attendance Failed", "No face detected in the image.")
        elif status == "multiple_faces":
            message = "Status: Multiple faces detected. Try again."
            self.show_popup("Attendance Failed", "Multiple faces detected. Please ensure only one face is visible.")
        else:
            # Handle any other unexpected statuses from backend
            message = f"Status: Unexpected response ({status})"
            self.show_popup("Error", f"Received unexpected status from server: {status} - {detail}")

        self.result_label.text = message
        self.capture_button.disabled = (self.camera is None) # Re-enable button (if camera exists)


    def go_back(self, instance):
        # on_leave handles stopping the camera
        self.manager.current = 'main'


    # --- Popup Helpers (reuse or adapt from RegisterScreen) ---
    def show_popup(self, title, message, auto_dismiss=False):
        """Helper to show simple popups."""
        self.dismiss_popup_if_exists() # Dismiss previous popup first

        popup_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        # Use text_size for wrapping long messages
        popup_layout.add_widget(Label(text=message, size_hint_y=None, height=dp(100), text_size=(dp(300), None)))
        close_button = Button(text='Close', size_hint_y=None, height=dp(40))
        popup_layout.add_widget(close_button)

        popup = Popup(title=title,
                      content=popup_layout,
                      size_hint=(0.8, None), # Auto height based on content
                      height=dp(200), # Set a reasonable default height
                      auto_dismiss=auto_dismiss)
        close_button.bind(on_press=popup.dismiss)

        popup.open()
        # Track the popup instance if needed for programmatic dismissal later
        self._active_popup = popup


    def dismiss_popup_if_exists(self):
        """Dismisses the currently tracked popup if it exists."""
        if hasattr(self, '_active_popup') and self._active_popup:
            try:
                self._active_popup.dismiss()
            except Exception as e:
                Logger.warning(f"Popup: Error dismissing popup: {e}")
            self._active_popup = None

class RegisterScreen(Screen):
    def __init__(self, **kwargs):
        super(RegisterScreen, self).__init__(**kwargs)
        self.image_captured = False
        self.temp_image_path = None # Path to temporarily saved image on tablet
        # No InsightFace or DB initialization here

    def on_enter(self):
        # --- Clear existing widgets if any ---
        self.clear_widgets()

        # Reset state
        self.image_captured = False
        self.temp_image_path = None

        # --- Build the UI dynamically ---
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        # Title
        title = Label(
            text='Register New User', font_size=dp(24), size_hint_y=None, height=dp(50)
        )
        main_layout.add_widget(title)

        # Form layout
        form_layout = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(120))

        # Employee Name
        form_layout.add_widget(Label(text='Employee Name:', halign='right'))
        self.name_input = TextInput(multiline=False, write_tab=False)
        form_layout.add_widget(self.name_input)

        # Employee ID
        form_layout.add_widget(Label(text='Employee ID:', halign='right'))
        self.id_input = TextInput(multiline=False, write_tab=False)
        form_layout.add_widget(self.id_input)

        main_layout.add_widget(form_layout)

        # Camera button
        self.camera_button = Button(
            text='Capture Face', background_color=get_color_from_hex('#2196F3'),
            size_hint_y=None, height=dp(50)
        )
        self.camera_button.bind(on_press=self.toggle_camera)
        main_layout.add_widget(self.camera_button)

        # Camera and preview area
        self.camera_layout = BoxLayout(orientation='vertical', spacing=dp(5)) # Added spacing

        # Camera widget - initially not added
        # Try index=0 first. If multiple cameras, you might need to adjust.
        # Handle potential camera initialization errors gracefully.
        try:
            self.camera = Camera(resolution=(640, 480), play=False, index=1)
            self.camera.rotation = -90  # or try -90 depending on your device

            # Set texture size explicitly if preview looks stretched/squashed
            # self.camera.texture_size = self.camera.resolution
        except Exception as e:
             Logger.error(f"Camera: Failed to initialize camera: {e}")
             self.camera = None # Flag that camera is unavailable
             self.show_popup("Camera Error", "Could not initialize camera device.")
             # Disable camera features if camera failed
             self.camera_button.disabled = True


        # Preview image
        self.preview = Image(
            source='', size_hint=(None, None), size=(dp(320), dp(240)),
            pos_hint={'center_x': 0.5}, allow_stretch=True, keep_ratio=True
        )

        # Will add either camera or preview to this layout
        self.camera_container = BoxLayout(size_hint_y=None, height=dp(240), pos_hint={'center_x': 0.5})
        self.camera_layout.add_widget(self.camera_container)

        # Capture button (only add if camera initialized)
        if self.camera:
            self.capture_button = Button(
                text='Take Photo', background_color=get_color_from_hex('#4CAF50'),
                size_hint_y=None, height=dp(50), disabled=True
            )
            self.capture_button.bind(on_press=self.capture_photo)
            self.camera_layout.add_widget(self.capture_button)
        else:
             self.capture_button = None # No capture button if no camera

        main_layout.add_widget(self.camera_layout)

        # Register and Back buttons
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        back_button = Button(text='Back to Main', background_color=get_color_from_hex('#9E9E9E'))
        back_button.bind(on_press=self.go_back)
        buttons_layout.add_widget(back_button)

        self.register_button = Button(text='Register User', background_color=get_color_from_hex('#FF9800'))
        self.register_button.bind(on_press=self.trigger_registration) # Renamed method
        buttons_layout.add_widget(self.register_button)

        main_layout.add_widget(buttons_layout)

        self.add_widget(main_layout)
        # No database creation here

    def toggle_camera(self, instance):
        if not self.camera: # Camera failed to init
            self.show_popup("Camera Error", "Camera is not available.")
            return

        if not self.camera.play:
            # Start camera
            try:
                self.camera_container.clear_widgets()
                # self.camera.index = 0 # Usually not needed unless switching
                self.camera.play = True
                self.camera_container.add_widget(self.camera) # Add camera widget
                self.camera_button.text = 'Cancel Capture'
                if self.capture_button:
                    self.capture_button.disabled = False
                Logger.info("Camera: Started.")
            except Exception as e:
                Logger.error(f"Camera: Error starting camera: {e}")
                self.show_popup("Camera Error", f"Could not start camera: {e}")
                self.camera.play = False # Ensure state is correct
                self.camera_container.clear_widgets()
                if self.preview.source and self.image_captured:
                    self.camera_container.add_widget(self.preview)
                self.camera_button.text = 'Capture Face'
                if self.capture_button:
                    self.capture_button.disabled = True
        else:
            # Stop camera
            self.camera.play = False
            self.camera_container.clear_widgets()
            if self.preview.source and self.image_captured:
                self.camera_container.add_widget(self.preview)
            self.camera_button.text = 'Capture Face' if not self.image_captured else 'Retake Photo'
            if self.capture_button:
                self.capture_button.disabled = True
            Logger.info("Camera: Stopped.")

    def capture_photo(self, instance):
        if not self.camera or not self.camera.play:
            Logger.warning("Capture: Attempted capture but camera is not active.")
            return

        try:
            # Use app's user_data_dir for temporary storage (platform-independent)
            app = App.get_running_app()
            # Ensure the directory exists within the app's safe space
            temp_dir = os.path.join(app.user_data_dir, 'temp_captures')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            timestamp = int(time.time())
            # Temporary filename, format doesn't matter much here as Kivy exports PNG
            self.temp_image_path = os.path.join(temp_dir, f"capture_{timestamp}.png")

            Logger.info(f"Capture: Saving temporary image to: {self.temp_image_path}")
            self.camera.export_to_png(self.temp_image_path)
            Logger.info(f"Capture: Successfully saved temporary PNG.")

            self.image_captured = True

            # --- Update UI ---
            self.camera.play = False

            # Show preview (use the temp path)
            self.preview.source = self.temp_image_path
            self.preview.reload() # Important to force reload
            self.camera_container.clear_widgets()
            self.camera_container.add_widget(self.preview)

            # Update buttons
            self.camera_button.text = 'Retake Photo'
            if self.capture_button:
                self.capture_button.disabled = True

        except Exception as e:
            Logger.error(f"Capture: Error during photo capture: {e}", exc_info=True)
            self.show_popup("Capture Error", f"Failed to capture photo: {e}")
            # Reset state partially
            self.temp_image_path = None
            self.image_captured = False
            if self.camera: self.camera.play = False # Ensure camera is stopped
            self.camera_container.clear_widgets()
            self.camera_button.text = 'Capture Face'
            if self.capture_button: self.capture_button.disabled = True

    def trigger_registration(self, instance):
        """Validates input and starts the registration thread."""
        name = self.name_input.text.strip()
        emp_id = self.id_input.text.strip()

        # --- Input Validation ---
        if not name or not emp_id:
            self.show_popup("Input Error", "Employee Name and ID are required.")
            return
        if not self.image_captured or not self.temp_image_path:
            self.show_popup("Input Error", "A face photo must be captured.")
            return
        if not os.path.exists(self.temp_image_path):
             self.show_popup("File Error", "Captured image file not found. Please recapture.")
             Logger.error(f"Register: Temp image path not found: {self.temp_image_path}")
             # Maybe clear the bad state
             self.image_captured = False
             self.temp_image_path = None
             self.preview.source = ''
             self.camera_container.clear_widgets()
             self.camera_button.text = 'Capture Face'
             return

        # Disable button to prevent multiple clicks
        self.register_button.disabled = True
        self.show_popup("Processing", "Registering user... Please wait.", auto_dismiss=False, add_close_button=False) # Show non-dismissible popup

        # Run the actual registration network call in a separate thread
        threading.Thread(target=self.register_user_thread, args=(name, emp_id, self.temp_image_path)).start()


    def register_user_thread(self, name, emp_id, image_path):
        """Sends registration data to the backend server (runs in a thread)."""
        files = None
        try:
            # Prepare data for multipart/form-data POST request
            data = {"name": name, "emp_id": emp_id}
            files = {'image': (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')}

            Logger.info(f"Register: Sending request to {REGISTER_ENDPOINT} for ID: {emp_id}")
            response = requests.post(REGISTER_ENDPOINT, data=data, files=files, timeout=30) # Added timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # If successful (status code 200)
            Logger.info(f"Register: Success for ID {emp_id}. Status: {response.status_code}")
            # Schedule UI updates on the main Kivy thread
            Clock.schedule_once(lambda dt: self.handle_registration_success(f"User '{name}' (ID: {emp_id}) registered successfully!"))

        except requests.exceptions.ConnectionError as e:
             Logger.error(f"Register: Connection error: {e}")
             Clock.schedule_once(lambda dt: self.handle_registration_error(f"Connection Error: Could not connect to the server at {BACKEND_URL}. Ensure it's running and the IP is correct."))
        except requests.exceptions.Timeout:
             Logger.error(f"Register: Request timed out")
             Clock.schedule_once(lambda dt: self.handle_registration_error("Connection Error: The request timed out. The server might be busy or unreachable."))
        except requests.exceptions.HTTPError as e:
            # Handle errors reported by the server (4xx, 5xx)
            error_msg = f"Registration failed (HTTP {response.status_code})"
            try:
                # Try to get detailed error from FastAPI response
                detail = response.json().get("detail", "No details provided.")
                error_msg += f": {detail}"
            except Exception: # Catch JSON decode errors etc.
                error_msg += f": {response.text}" # Show raw text if JSON fails
            Logger.error(f"Register: HTTP error for ID {emp_id}: {error_msg}")
            Clock.schedule_once(lambda dt: self.handle_registration_error(error_msg))
        except Exception as e:
            # Catch other unexpected errors (file reading issues, etc.)
            Logger.error(f"Register: Unexpected error during registration for ID {emp_id}: {e}", exc_info=True)
            Clock.schedule_once(lambda dt: self.handle_registration_error(f"An unexpected error occurred: {e}"))
        finally:
            # Ensure the file handle is closed if it was opened
            if files and 'image' in files and files['image']:
                try:
                    files['image'][1].close()
                except Exception as e:
                    Logger.error(f"Register: Error closing image file handle: {e}")
            # Schedule re-enabling the button and dismissing the "Processing" popup
            Clock.schedule_once(lambda dt: self.finalize_registration_ui())
            # Clean up the temporary image file after attempt
            try:
                 if os.path.exists(image_path):
                     os.remove(image_path)
                     Logger.info(f"Register: Cleaned up temporary file: {image_path}")
            except Exception as e:
                 Logger.error(f"Register: Failed to clean up temp file {image_path}: {e}")


    def handle_registration_success(self, message):
        """Called via Clock schedule on successful registration."""
        self.dismiss_popup_if_exists("Processing") # Dismiss "Processing" popup
        self.show_popup("Success", message)
        self.clear_registration_form()

    def handle_registration_error(self, message):
        """Called via Clock schedule on registration error."""
        self.dismiss_popup_if_exists("Processing") # Dismiss "Processing" popup
        self.show_popup("Error", message)
        # Don't clear the form on error, let the user correct it

    def finalize_registration_ui(self):
        """Re-enables the register button and potentially dismisses processing popups."""
        self.dismiss_popup_if_exists("Processing")
        self.register_button.disabled = False


    def clear_registration_form(self):
        """Clears the input fields and image preview."""
        Logger.info("UI: Clearing registration form.")
        if hasattr(self, 'name_input'):
            self.name_input.text = ''
        if hasattr(self, 'id_input'):
            self.id_input.text = ''
        if hasattr(self, 'preview'):
            self.preview.source = '' # Clear preview image
        if hasattr(self, 'camera_container'):
             self.camera_container.clear_widgets() # Remove preview/camera widget

        # Reset buttons to initial state
        if hasattr(self, 'camera_button'):
             self.camera_button.text = 'Capture Face'
             # Ensure camera button is enabled if camera exists
             self.camera_button.disabled = (self.camera is None)
        if hasattr(self, 'capture_button') and self.capture_button:
             self.capture_button.disabled = True # Take photo button always disabled initially

        self.image_captured = False
        # No need to delete temp_image_path here, thread cleans it up
        self.temp_image_path = None


    def go_back(self, instance):
        # Stop camera if playing
        if hasattr(self, 'camera') and self.camera and self.camera.play:
            self.camera.play = False
            Logger.info("Camera: Stopped on navigating back.")
        # Optional: Clear form when going back
        # self.clear_registration_form()
        self.manager.current = 'main'

    # --- Popup Helpers ---
    def show_popup(self, title, message, auto_dismiss=False, add_close_button=True):
        """Helper to show simple popups. Tracks the currently open popup."""
        # Dismiss any existing popup first, unless it's the one we track
        self.dismiss_popup_if_exists(title_to_avoid=title if not auto_dismiss else None)

        popup_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        popup_layout.add_widget(Label(text=message, size_hint_y=None, height=dp(80), text_size=(dp(300), None))) # Allow wrapping

        if add_close_button:
            close_button = Button(text='Close', size_hint_y=None, height=dp(40))
            popup_layout.add_widget(close_button)

        popup = Popup(title=title,
                        content=popup_layout,
                        size_hint=(0.8, None), # Adjust height automatically
                        height=dp(200) if add_close_button else dp(150),
                        auto_dismiss=auto_dismiss)

        if add_close_button:
            close_button.bind(on_press=popup.dismiss)

        popup.open()
        # Store reference to non-auto-dismiss popups to dismiss them programmatically
        if not auto_dismiss:
            self._active_popup = popup
            self._active_popup_title = title


    def dismiss_popup_if_exists(self, title_to_avoid=None):
        """Dismisses the tracked popup if it exists and title doesn't match avoid title."""
        if hasattr(self, '_active_popup') and self._active_popup:
             if title_to_avoid is None or self._active_popup_title != title_to_avoid:
                 try:
                     self._active_popup.dismiss()
                 except Exception as e:
                     Logger.warning(f"Popup: Error dismissing popup: {e}")
                 self._active_popup = None
                 self._active_popup_title = None


    def on_leave(self):
        # Ensure camera is stopped when leaving the screen
        if hasattr(self, 'camera') and self.camera and self.camera.play:
            self.camera.play = False
            Logger.info("Camera: Stopped on leaving RegisterScreen.")
        # Clean up any lingering popups
        self.dismiss_popup_if_exists()

class AdminScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        # Title
        title = Label(text="Admin Panel - Attendance Log", size_hint_y=None, height=dp(40), font_size=dp(20))
        self.layout.add_widget(title)

        # ScrollView for the table data
        scroll_view = ScrollView(size_hint=(1, 1)) # Fill available space

        # GridLayout for the table structure
        self.data_grid = GridLayout(
            cols=5, # Emp ID, Name, Date, In-Time, Out-Time
            spacing=dp(5),
            size_hint_y=None # Important for ScrollView
        )
        # Make the GridLayout height fit its content
        self.data_grid.bind(minimum_height=self.data_grid.setter('height'))

        scroll_view.add_widget(self.data_grid)
        self.layout.add_widget(scroll_view) # Add ScrollView to main layout

        # Back Button
        back_button = Button(text="Back to Main", size_hint_y=None, height=dp(50))
        back_button.bind(on_press=self.go_back)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def on_enter(self):
        """Called when the screen is displayed. Triggers data fetching."""
        self.fetch_and_display_log()

    def show_loading_message(self, message="Loading..."):
        """Clears grid and shows a loading message."""
        self.data_grid.clear_widgets()
        # Add a single label spanning all columns (GridLayout doesn't support colspan easily)
        # So, we add one label and empty ones to fill the row.
        loading_label = Label(text=message, size_hint_y=None, height=dp(30), bold=True)
        self.data_grid.add_widget(loading_label)
        for _ in range(self.data_grid.cols - 1):
             self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))


    def fetch_and_display_log(self):
        """Shows loading message and starts the fetching thread."""
        self.show_loading_message("Loading attendance data...")
        # Run the network request in a thread
        threading.Thread(target=self.fetch_log_thread).start()


    def fetch_log_thread(self):
        """Fetches attendance log data from the backend API."""
        fetched_data = None
        error_message = None
        try:
            Logger.info(f"AdminScreen: Fetching data from {ATTENDANCE_LOG_ENDPOINT}")
            response = requests.get(ATTENDANCE_LOG_ENDPOINT, timeout=20) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            fetched_data = response.json() # Expecting a list of dicts
            Logger.info(f"AdminScreen: Successfully fetched {len(fetched_data)} records.")

        except requests.exceptions.ConnectionError as e:
             Logger.error(f"AdminScreen: Connection error: {e}")
             error_message = f"Connection Error: Could not connect to the server at {BACKEND_URL}."
        except requests.exceptions.Timeout:
             Logger.error(f"AdminScreen: Request timed out")
             error_message = "Connection Error: The request timed out."
        except requests.exceptions.HTTPError as e:
            error_msg_detail = f"Server error (HTTP {response.status_code})"
            try:
                detail = response.json().get("detail", response.text)
                error_msg_detail += f": {detail}"
            except Exception:
                error_msg_detail += f": {response.text}"
            Logger.error(f"AdminScreen: HTTP error: {error_msg_detail}")
            error_message = error_msg_detail
        except requests.exceptions.JSONDecodeError:
            Logger.error(f"AdminScreen: Failed to decode JSON response.")
            error_message = "Error: Invalid data format received from server."
        except Exception as e:
            Logger.error(f"AdminScreen: Unexpected error fetching log: {e}", exc_info=True)
            error_message = f"An unexpected error occurred: {e}"

        # Schedule the UI update back on the main thread
        Clock.schedule_once(lambda dt: self.update_grid(fetched_data, error_message))


    def update_grid(self, records, error_message):
        """Populates the grid with fetched data or shows an error."""
        self.data_grid.clear_widgets() # Clear previous data/loading message

        # Add Header Row
        headers = ["Emp ID", "Name", "Date", "In Time", "Out Time"]
        for header in headers:
            self.data_grid.add_widget(Label(text=header, bold=True, size_hint_y=None, height=dp(30)))

        # Handle errors first
        if error_message:
            Logger.error(f"AdminScreen: Displaying error: {error_message}")
            error_label = Label(text=error_message, color=(1, 0, 0, 1), size_hint_y=None, height=dp(30))
            self.data_grid.add_widget(error_label)
            # Fill the rest of the row with empty labels
            for _ in range(self.data_grid.cols - 1):
                self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
            return # Stop processing

        # Check if data was received (records might be None if fetch failed before error message)
        if records is None:
             # Should have been caught by error_message, but as a safeguard
             Logger.warning("AdminScreen: update_grid called with records=None and no error message.")
             no_data_label = Label(text="Failed to fetch data.", color=(1, 0, 0, 1), size_hint_y=None, height=dp(30))
             self.data_grid.add_widget(no_data_label)
             for _ in range(self.data_grid.cols - 1):
                 self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
             return

        # Handle empty list
        if not records:
            Logger.info("AdminScreen: No attendance records found.")
            no_records_label = Label(text="No attendance records found.", size_hint_y=None, height=dp(30))
            self.data_grid.add_widget(no_records_label)
            # Fill the rest of the row
            for _ in range(self.data_grid.cols - 1):
                self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
            return

        # Populate Grid with fetched data
        Logger.info(f"AdminScreen: Populating grid with {len(records)} records.")
        for record in records:
            # Extract data safely using .get() with defaults
            emp_id = record.get('emp_id', 'N/A')
            name = record.get('name', 'N/A')
            date_str = record.get('date', 'N/A')
            in_time = record.get('in_time') # Get value, could be None
            out_time = record.get('out_time') # Get value, could be None

            # Handle None values for display
            in_time_str = str(in_time) if in_time is not None else "-"
            out_time_str = str(out_time) if out_time is not None else "-"

            # Add labels for the row
            self.data_grid.add_widget(Label(text=str(emp_id), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=str(name), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=str(date_str), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=in_time_str, size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=out_time_str, size_hint_y=None, height=dp(30)))

    def go_back(self, instance):
        self.manager.current = 'main' # Navigate back to your main screen name

class AttendanceApp(App):
    def build(self):
        # Create screen manager
        if platform == 'android':
            try:
                request_permissions([
                    Permission.CAMERA,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE
                ])
            except Exception as e:
                print(f"Permission request failed: {e}")

        sm = ScreenManager()
        
        # Add screens
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(RegisterScreen(name='register'))
        sm.add_widget(AttendanceScreen(name='attendance'))
        sm.add_widget(AdminScreen(name='admin_records'))

        return sm

if __name__ == '__main__':
    # Set default window size for development
    if platform != 'android':  # Only set window size for desktop
        Window.size = (600, 800)
    AttendanceApp().run()
