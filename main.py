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
from kivy.clock import Clock 
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
import os
import time
import requests 
import threading 
from PIL import Image as PILImage 
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.camera import Camera
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.logger import Logger
from kivy.graphics.transformation import Matrix 
from kivy.utils import platform


from kivy.utils import platform

if platform == 'android':
    try:
        from android.permissions import request_permissions, Permission
    except ImportError:
        print("Warning: android.permissions module not available outside Android.")

ADMIN_PASSWORD = "123" #can be changed, hard coded for trial purposes
BACKEND_URL = "http://{your-pc-ip}:8000"  #replace your pc ip here
REGISTER_ENDPOINT = f"{BACKEND_URL}/register"
RECOGNIZE_ENDPOINT = f"{BACKEND_URL}/recognize_attendance"
ATTENDANCE_LOG_ENDPOINT = f"{BACKEND_URL}/attendance_log"


class ResponsiveButton(Button):
    min_height = NumericProperty(dp(60))
    
    def __init__(self, **kwargs):
        super(ResponsiveButton, self).__init__(**kwargs)
        self.bind(size=self.update_text_size)
    
    def update_text_size(self, instance, size):
        
        width_factor = self.width * 0.03
        height_factor = self.height * 0.4
        self.font_size = min(width_factor, height_factor)
        
        
        self.text_size = (self.width * 0.9, None)

class MainScreen(Screen):
    def __init__(self, **kwargs):
        super(MainScreen, self).__init__(**kwargs)
        self.layout = BoxLayout(
            orientation='vertical',
            padding=[Window.width * 0.05, Window.height * 0.05],
            spacing=Window.height * 0.03
        )
        
        
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
        

        
        self.layout.add_widget(self.button1)
        self.layout.add_widget(self.button2)
        self.layout.add_widget(self.button3)
        
        
        Window.bind(size=self.update_layout_padding)
        
        self.add_widget(self.layout)
    
    def update_layout_padding(self, instance, size):
        
        self.layout.padding = [size[0] * 0.05, size[1] * 0.05]
        self.layout.spacing = size[1] * 0.03
        
    def open_register_screen(self, instance):
        self.manager.current = 'register'

    def open_attendance_screen(self, instance):
        self.manager.current = 'attendance'


    def show_admin_login_popup(self, instance):
        
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
        self.error_label = Label(text='', color=(1, 0, 0, 1), size_hint_y=None, height=dp(30)) 

        popup_content.add_widget(Label(text='Admin Access Required'))
        popup_content.add_widget(password_input)
        popup_content.add_widget(self.error_label) 
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

        
        submit_button.bind(on_press=lambda *args: self.check_admin_password(password_input.text, popup))
        cancel_button.bind(on_press=popup.dismiss)

        popup.open()

    def check_admin_password(self, entered_password, popup):
        
        if entered_password == ADMIN_PASSWORD:
            print("Admin access granted.")
            popup.dismiss()
            
            self.manager.current = 'admin_records'
        else:
            print("Admin access denied: Incorrect password.")
            
            self.error_label.text = "Incorrect Password!"


class AttendanceScreen(Screen):
    def __init__(self, **kwargs):
        super(AttendanceScreen, self).__init__(**kwargs)
        
        self.temp_image_path = None 

        
        
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        title_label = Label(
            text='Point Camera at Face for Attendance',
            font_size=dp(24),
            size_hint_y=None,
            height=dp(50)
        )
        main_layout.add_widget(title_label)

        
        camera_container = BoxLayout(size_hint_y=1) 

        
        try:

            cam_index = 1 if platform == 'android' else 0
            self.camera = Camera(resolution=(640, 480), play=False, index=cam_index)
            self.camera.transform = Matrix().rotate(1.5708, 0, 0, 1)  

        except Exception as e:
            Logger.error(f"AttendanceScreen: Failed to initialize camera: {e}")
            self.camera = None 
            

        if self.camera:
            camera_container.add_widget(self.camera)
        else:
            
            camera_container.add_widget(Label(text="Camera not available", color=(1,0,0,1)))

        main_layout.add_widget(camera_container)

        
        self.capture_button = Button(
            text='Mark Attendance (Check-in / Check-out)',
            size_hint_y=None, height=dp(60),
            background_color=get_color_from_hex('#4CAF50'),
            disabled=(self.camera is None) 
        )
        self.capture_button.bind(on_press=self.trigger_attendance_check)
        main_layout.add_widget(self.capture_button)

        
        self.result_label = Label(
            text='Status: Ready',
            font_size=dp(18),
            size_hint_y=None,
            height=dp(40)
        )
        main_layout.add_widget(self.result_label)

        
        self.back_button = Button(
            text='Back to Main',
            size_hint_y=None,
            height=dp(50),
            background_color=get_color_from_hex('#9E9E9E')
        )
        self.back_button.bind(on_press=self.go_back)
        main_layout.add_widget(self.back_button)

        self.add_widget(main_layout)
        

    def on_enter(self, *args):
        self.result_label.text = 'Status: Ready'
        self.temp_image_path = None  

        if self.camera:
            Logger.info("AttendanceScreen: Scheduling delayed camera start.")
            Clock.schedule_once(lambda dt: self.start_camera_safely(), 0.5)
        else:
            self.result_label.text = "Status: Camera unavailable"
            self.capture_button.disabled = True
            Logger.warning("AttendanceScreen: Camera is None.")
            self.show_popup("Camera Error", "Camera device could not be initialized.")

        def on_leave(self, *args):
            
            if hasattr(self, 'camera') and self.camera and self.camera.play:
                self.camera.play = False
                Logger.info("AttendanceScreen: Camera stopped.")
            
            self.dismiss_popup_if_exists()

    def start_camera_safely(self):
        try:
            self.camera.transform = Matrix().rotate(1.5708, 0, 0, 1)  
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
        
        if not self.camera or not self.camera.play:
            self.result_label.text = "Error: Camera not active."
            Logger.warning("Attendance: Capture failed, camera not playing.")
            return

        
        instance.disabled = True
        self.result_label.text = "Processing..."

        try:
            
            app = App.get_running_app()
            temp_dir = os.path.join(app.user_data_dir, 'temp_attendance')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            timestamp = int(time.time())
            self.temp_image_path = os.path.join(temp_dir, f"attendance_{timestamp}.png")

            Logger.info(f"Attendance: Capturing temporary image to: {self.temp_image_path}")
            self.camera.export_to_png(self.temp_image_path)
            Logger.info(f"Attendance: Successfully saved temporary PNG.")

            
            threading.Thread(target=self.attendance_check_thread, args=(self.temp_image_path,)).start()

        except Exception as e:
            Logger.error(f"Attendance: Error during photo capture: {e}", exc_info=True)
            self.result_label.text = f"Error capturing photo: {e}"
            self.show_popup("Capture Error", f"Failed to capture photo: {e}")
            instance.disabled = False 
            self.temp_image_path = None 


    def attendance_check_thread(self, image_path):
        
        files = None
        response_data = {"status": "error", "detail": "Unknown error"} 

        try:
            if not os.path.exists(image_path):
                 raise FileNotFoundError(f"Temporary image file not found at {image_path}")

            files = {'image': (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')}

            Logger.info(f"Attendance: Sending request to {RECOGNIZE_ENDPOINT}")
            response = requests.post(RECOGNIZE_ENDPOINT, files=files, timeout=30) 
            response.raise_for_status() 

            
            response_data = response.json() 
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
                
                detail = response.json().get("detail", response.text) 
                error_msg += f": {detail}"
                
                response_data = response.json() if response.headers.get('content-type') == 'application/json' else {"status": "error", "detail": detail}
                if "status" not in response_data: response_data["status"] = "error" 
            except Exception:
                 response_data = {"status": "error", "detail": error_msg + f": {response.text}"}
            Logger.error(f"Attendance: HTTP error: {error_msg}")
        except Exception as e:
            Logger.error(f"Attendance: Unexpected error during check: {e}", exc_info=True)
            response_data = {"status": "error", "detail": f"An unexpected client error occurred: {e}"}
        finally:
            
            if files and 'image' in files and files['image']:
                try:
                    files['image'][1].close()
                except Exception as e:
                    Logger.error(f"Attendance: Error closing image file handle: {e}")

            
            try:
                 if os.path.exists(image_path):
                     os.remove(image_path)
                     Logger.info(f"Attendance: Cleaned up temporary file: {image_path}")
            except Exception as e:
                 Logger.error(f"Attendance: Failed to clean up temp file {image_path}: {e}")

            
            Clock.schedule_once(lambda dt: self.handle_attendance_response(response_data))


    def handle_attendance_response(self, response_data):
        
        status = response_data.get("status", "error")
        name = response_data.get("name", "") 
        detail = response_data.get("detail", "An unknown error occurred.")

        message = f"Status: {status}" 

        if status == "check_in_success":
            message = f"Welcome, {name}! Check-in recorded."
            self.show_popup("Attendance Success", message)
        elif status == "check_out_success":
            message = f"Goodbye, {name}! Check-out recorded."
            self.show_popup("Attendance Success", message)
        elif status == "already_checked_out":
             message = f"Status: {name}, you already checked out today."
             self.show_popup("Attendance Info", message)
        elif status == "already_checked_in": 
             message = f"Status: {name}, you are already checked in."
             self.show_popup("Attendance Info", message)
        elif status == "not_recognized":
            message = "Status: Face not recognized. Please try again."
            self.show_popup("Attendance Failed", "Face not recognized.")
        elif status == "error":
            message = f"Error: {detail}"
            self.show_popup("Attendance Error", message) 
            message = "Status: Error occurred" 
        elif status == "no_face":
            message = "Status: No face detected. Try again."
            self.show_popup("Attendance Failed", "No face detected in the image.")
        elif status == "multiple_faces":
            message = "Status: Multiple faces detected. Try again."
            self.show_popup("Attendance Failed", "Multiple faces detected. Please ensure only one face is visible.")
        else:
            
            message = f"Status: Unexpected response ({status})"
            self.show_popup("Error", f"Received unexpected status from server: {status} - {detail}")

        self.result_label.text = message
        self.capture_button.disabled = (self.camera is None) 


    def go_back(self, instance):
        
        self.manager.current = 'main'


    
    def show_popup(self, title, message, auto_dismiss=False):
        
        self.dismiss_popup_if_exists() 

        popup_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        popup_layout.add_widget(Label(text=message, size_hint_y=None, height=dp(100), text_size=(dp(300), None)))
        close_button = Button(text='Close', size_hint_y=None, height=dp(40))
        popup_layout.add_widget(close_button)

        popup = Popup(title=title,
                      content=popup_layout,
                      size_hint=(0.8, None), 
                      height=dp(200), 
                      auto_dismiss=auto_dismiss)
        close_button.bind(on_press=popup.dismiss)

        popup.open()
        
        self._active_popup = popup


    def dismiss_popup_if_exists(self):
        
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
        self.temp_image_path = None 
        

    def on_enter(self):
        
        self.clear_widgets()

        
        self.image_captured = False
        self.temp_image_path = None

        
        main_layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))

        
        title = Label(
            text='Register New User', font_size=dp(24), size_hint_y=None, height=dp(50)
        )
        main_layout.add_widget(title)

        
        form_layout = GridLayout(cols=2, spacing=dp(10), size_hint_y=None, height=dp(120))

        
        form_layout.add_widget(Label(text='Employee Name:', halign='right'))
        self.name_input = TextInput(multiline=False, write_tab=False)
        form_layout.add_widget(self.name_input)

        
        form_layout.add_widget(Label(text='Employee ID:', halign='right'))
        self.id_input = TextInput(multiline=False, write_tab=False)
        form_layout.add_widget(self.id_input)

        main_layout.add_widget(form_layout)

        
        self.camera_button = Button(
            text='Capture Face', background_color=get_color_from_hex('#2196F3'),
            size_hint_y=None, height=dp(50)
        )
        self.camera_button.bind(on_press=self.toggle_camera)
        main_layout.add_widget(self.camera_button)

        
        self.camera_layout = BoxLayout(orientation='vertical', spacing=dp(5)) 

        
        
        
        try:
            cam_index = 1 if platform == 'android' else 0
            self.camera = Camera(resolution=(640, 480), play=False, index=cam_index)
            self.camera.transform = Matrix().rotate(1.5708, 0, 0, 1)  

            
            
        except Exception as e:
             Logger.error(f"Camera: Failed to initialize camera: {e}")
             self.camera = None 
             self.show_popup("Camera Error", "Could not initialize camera device.")
             
             self.camera_button.disabled = True


        
        self.preview = Image(
            source='', size_hint=(None, None), size=(dp(320), dp(240)),
            pos_hint={'center_x': 0.5}, allow_stretch=True, keep_ratio=True
        )

        
        self.camera_container = BoxLayout(size_hint_y=None, height=dp(240), pos_hint={'center_x': 0.5})
        self.camera_layout.add_widget(self.camera_container)

        
        if self.camera:
            self.capture_button = Button(
                text='Take Photo', background_color=get_color_from_hex('#4CAF50'),
                size_hint_y=None, height=dp(50), disabled=True
            )
            self.capture_button.bind(on_press=self.capture_photo)
            self.camera_layout.add_widget(self.capture_button)
        else:
             self.capture_button = None 

        main_layout.add_widget(self.camera_layout)

        
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))

        back_button = Button(text='Back to Main', background_color=get_color_from_hex('#9E9E9E'))
        back_button.bind(on_press=self.go_back)
        buttons_layout.add_widget(back_button)

        self.register_button = Button(text='Register User', background_color=get_color_from_hex('#FF9800'))
        self.register_button.bind(on_press=self.trigger_registration) 
        buttons_layout.add_widget(self.register_button)

        main_layout.add_widget(buttons_layout)

        self.add_widget(main_layout)
        

    def toggle_camera(self, instance):
        if not self.camera: 
            self.show_popup("Camera Error", "Camera is not available.")
            return

        if not self.camera.play:
            
            try:
                self.camera_container.clear_widgets()
                
                self.camera.play = True
                self.camera_container.add_widget(self.camera) 
                self.camera_button.text = 'Cancel Capture'
                if self.capture_button:
                    self.capture_button.disabled = False
                Logger.info("Camera: Started.")
            except Exception as e:
                Logger.error(f"Camera: Error starting camera: {e}")
                self.show_popup("Camera Error", f"Could not start camera: {e}")
                self.camera.play = False 
                self.camera_container.clear_widgets()
                if self.preview.source and self.image_captured:
                    self.camera_container.add_widget(self.preview)
                self.camera_button.text = 'Capture Face'
                if self.capture_button:
                    self.capture_button.disabled = True
        else:
            
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
            
            app = App.get_running_app()
            
            temp_dir = os.path.join(app.user_data_dir, 'temp_captures')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            timestamp = int(time.time())
            
            self.temp_image_path = os.path.join(temp_dir, f"capture_{timestamp}.png")

            Logger.info(f"Capture: Saving temporary image to: {self.temp_image_path}")
            self.camera.export_to_png(self.temp_image_path)
            Logger.info(f"Capture: Successfully saved temporary PNG.")

            self.image_captured = True

            
            self.camera.play = False

            
            self.preview.source = self.temp_image_path
            self.preview.reload() 
            self.camera_container.clear_widgets()
            self.camera_container.add_widget(self.preview)

            
            self.camera_button.text = 'Retake Photo'
            if self.capture_button:
                self.capture_button.disabled = True

        except Exception as e:
            Logger.error(f"Capture: Error during photo capture: {e}", exc_info=True)
            self.show_popup("Capture Error", f"Failed to capture photo: {e}")
            
            self.temp_image_path = None
            self.image_captured = False
            if self.camera: self.camera.play = False 
            self.camera_container.clear_widgets()
            self.camera_button.text = 'Capture Face'
            if self.capture_button: self.capture_button.disabled = True

    def trigger_registration(self, instance):
        
        name = self.name_input.text.strip()
        emp_id = self.id_input.text.strip()

        
        if not name or not emp_id:
            self.show_popup("Input Error", "Employee Name and ID are required.")
            return
        if not self.image_captured or not self.temp_image_path:
            self.show_popup("Input Error", "A face photo must be captured.")
            return
        if not os.path.exists(self.temp_image_path):
             self.show_popup("File Error", "Captured image file not found. Please recapture.")
             Logger.error(f"Register: Temp image path not found: {self.temp_image_path}")
             
             self.image_captured = False
             self.temp_image_path = None
             self.preview.source = ''
             self.camera_container.clear_widgets()
             self.camera_button.text = 'Capture Face'
             return

        
        self.register_button.disabled = True
        self.show_popup("Processing", "Registering user... Please wait.", auto_dismiss=False, add_close_button=False) 

        
        threading.Thread(target=self.register_user_thread, args=(name, emp_id, self.temp_image_path)).start()


    def register_user_thread(self, name, emp_id, image_path):
        
        files = None
        try:
            
            data = {"name": name, "emp_id": emp_id}
            files = {'image': (os.path.basename(image_path), open(image_path, 'rb'), 'image/png')}

            Logger.info(f"Register: Sending request to {REGISTER_ENDPOINT} for ID: {emp_id}")
            response = requests.post(REGISTER_ENDPOINT, data=data, files=files, timeout=30) 
            response.raise_for_status() 

            
            Logger.info(f"Register: Success for ID {emp_id}. Status: {response.status_code}")
            
            Clock.schedule_once(lambda dt: self.handle_registration_success(f"User '{name}' (ID: {emp_id}) registered successfully!"))

        except requests.exceptions.ConnectionError as e:
             Logger.error(f"Register: Connection error: {e}")
             Clock.schedule_once(lambda dt: self.handle_registration_error(f"Connection Error: Could not connect to the server at {BACKEND_URL}. Ensure it's running and the IP is correct."))
        except requests.exceptions.Timeout:
             Logger.error(f"Register: Request timed out")
             Clock.schedule_once(lambda dt: self.handle_registration_error("Connection Error: The request timed out. The server might be busy or unreachable."))
        except requests.exceptions.HTTPError as e:
            
            error_msg = f"Registration failed (HTTP {response.status_code})"
            try:
                
                detail = response.json().get("detail", "No details provided.")
                error_msg += f": {detail}"
            except Exception: 
                error_msg += f": {response.text}" 
            Logger.error(f"Register: HTTP error for ID {emp_id}: {error_msg}")
            Clock.schedule_once(lambda dt: self.handle_registration_error(error_msg))
        except Exception as e:
            
            Logger.error(f"Register: Unexpected error during registration for ID {emp_id}: {e}", exc_info=True)
            Clock.schedule_once(lambda dt: self.handle_registration_error(f"An unexpected error occurred: {e}"))
        finally:
            
            if files and 'image' in files and files['image']:
                try:
                    files['image'][1].close()
                except Exception as e:
                    Logger.error(f"Register: Error closing image file handle: {e}")
            
            Clock.schedule_once(lambda dt: self.finalize_registration_ui())
            
            try:
                 if os.path.exists(image_path):
                     os.remove(image_path)
                     Logger.info(f"Register: Cleaned up temporary file: {image_path}")
            except Exception as e:
                 Logger.error(f"Register: Failed to clean up temp file {image_path}: {e}")


    def handle_registration_success(self, message):
        
        self.dismiss_popup_if_exists("Processing") 
        self.show_popup("Success", message)
        self.clear_registration_form()

    def handle_registration_error(self, message):
        
        self.dismiss_popup_if_exists("Processing") 
        self.show_popup("Error", message)
        

    def finalize_registration_ui(self):
        
        self.dismiss_popup_if_exists("Processing")
        self.register_button.disabled = False


    def clear_registration_form(self):
        
        Logger.info("UI: Clearing registration form.")
        if hasattr(self, 'name_input'):
            self.name_input.text = ''
        if hasattr(self, 'id_input'):
            self.id_input.text = ''
        if hasattr(self, 'preview'):
            self.preview.source = '' 
        if hasattr(self, 'camera_container'):
             self.camera_container.clear_widgets() 

        
        if hasattr(self, 'camera_button'):
             self.camera_button.text = 'Capture Face'
             
             self.camera_button.disabled = (self.camera is None)
        if hasattr(self, 'capture_button') and self.capture_button:
             self.capture_button.disabled = True 

        self.image_captured = False
        
        self.temp_image_path = None


    def go_back(self, instance):
        
        if hasattr(self, 'camera') and self.camera and self.camera.play:
            self.camera.play = False
            Logger.info("Camera: Stopped on navigating back.")
        
        
        self.manager.current = 'main'

    
    def show_popup(self, title, message, auto_dismiss=False, add_close_button=True):
        
        
        self.dismiss_popup_if_exists(title_to_avoid=title if not auto_dismiss else None)

        popup_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        popup_layout.add_widget(Label(text=message, size_hint_y=None, height=dp(80), text_size=(dp(300), None))) 

        if add_close_button:
            close_button = Button(text='Close', size_hint_y=None, height=dp(40))
            popup_layout.add_widget(close_button)

        popup = Popup(title=title,
                        content=popup_layout,
                        size_hint=(0.8, None), 
                        height=dp(200) if add_close_button else dp(150),
                        auto_dismiss=auto_dismiss)

        if add_close_button:
            close_button.bind(on_press=popup.dismiss)

        popup.open()
        
        if not auto_dismiss:
            self._active_popup = popup
            self._active_popup_title = title


    def dismiss_popup_if_exists(self, title_to_avoid=None):
        
        if hasattr(self, '_active_popup') and self._active_popup:
             if title_to_avoid is None or self._active_popup_title != title_to_avoid:
                 try:
                     self._active_popup.dismiss()
                 except Exception as e:
                     Logger.warning(f"Popup: Error dismissing popup: {e}")
                 self._active_popup = None
                 self._active_popup_title = None


    def on_leave(self):
        
        if hasattr(self, 'camera') and self.camera and self.camera.play:
            self.camera.play = False
            Logger.info("Camera: Stopped on leaving RegisterScreen.")
        
        self.dismiss_popup_if_exists()

class AdminScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        
        title = Label(text="Admin Panel - Attendance Log", size_hint_y=None, height=dp(40), font_size=dp(20))
        self.layout.add_widget(title)

        
        scroll_view = ScrollView(size_hint=(1, 1)) 

        
        self.data_grid = GridLayout(
            cols=5, 
            spacing=dp(5),
            size_hint_y=None 
        )
        
        self.data_grid.bind(minimum_height=self.data_grid.setter('height'))

        scroll_view.add_widget(self.data_grid)
        self.layout.add_widget(scroll_view) 

        
        back_button = Button(text="Back to Main", size_hint_y=None, height=dp(50))
        back_button.bind(on_press=self.go_back)
        self.layout.add_widget(back_button)

        self.add_widget(self.layout)

    def on_enter(self):
        
        self.fetch_and_display_log()

    def show_loading_message(self, message="Loading..."):
        
        self.data_grid.clear_widgets()
        
        
        loading_label = Label(text=message, size_hint_y=None, height=dp(30), bold=True)
        self.data_grid.add_widget(loading_label)
        for _ in range(self.data_grid.cols - 1):
             self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))


    def fetch_and_display_log(self):
        
        self.show_loading_message("Loading attendance data...")
        
        threading.Thread(target=self.fetch_log_thread).start()


    def fetch_log_thread(self):
        
        fetched_data = None
        error_message = None
        try:
            Logger.info(f"AdminScreen: Fetching data from {ATTENDANCE_LOG_ENDPOINT}")
            response = requests.get(ATTENDANCE_LOG_ENDPOINT, timeout=20) 
            response.raise_for_status() 

            fetched_data = response.json() 
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

        
        Clock.schedule_once(lambda dt: self.update_grid(fetched_data, error_message))


    def update_grid(self, records, error_message):
        
        self.data_grid.clear_widgets() 

        
        headers = ["Emp ID", "Name", "Date", "In Time", "Out Time"]
        for header in headers:
            self.data_grid.add_widget(Label(text=header, bold=True, size_hint_y=None, height=dp(30)))

        
        if error_message:
            Logger.error(f"AdminScreen: Displaying error: {error_message}")
            error_label = Label(text=error_message, color=(1, 0, 0, 1), size_hint_y=None, height=dp(30))
            self.data_grid.add_widget(error_label)
            
            for _ in range(self.data_grid.cols - 1):
                self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
            return 

        
        if records is None:
             
             Logger.warning("AdminScreen: update_grid called with records=None and no error message.")
             no_data_label = Label(text="Failed to fetch data.", color=(1, 0, 0, 1), size_hint_y=None, height=dp(30))
             self.data_grid.add_widget(no_data_label)
             for _ in range(self.data_grid.cols - 1):
                 self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
             return

        
        if not records:
            Logger.info("AdminScreen: No attendance records found.")
            no_records_label = Label(text="No attendance records found.", size_hint_y=None, height=dp(30))
            self.data_grid.add_widget(no_records_label)
            
            for _ in range(self.data_grid.cols - 1):
                self.data_grid.add_widget(Label(text="", size_hint_y=None, height=dp(30)))
            return

        
        Logger.info(f"AdminScreen: Populating grid with {len(records)} records.")
        for record in records:
            
            emp_id = record.get('emp_id', 'N/A')
            name = record.get('name', 'N/A')
            date_str = record.get('date', 'N/A')
            in_time = record.get('in_time') 
            out_time = record.get('out_time') 

            
            in_time_str = str(in_time) if in_time is not None else "-"
            out_time_str = str(out_time) if out_time is not None else "-"

            
            self.data_grid.add_widget(Label(text=str(emp_id), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=str(name), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=str(date_str), size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=in_time_str, size_hint_y=None, height=dp(30)))
            self.data_grid.add_widget(Label(text=out_time_str, size_hint_y=None, height=dp(30)))

    def go_back(self, instance):
        self.manager.current = 'main' 

class AttendanceApp(App):
    def build(self):
        
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
        
        
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(RegisterScreen(name='register'))
        sm.add_widget(AttendanceScreen(name='attendance'))
        sm.add_widget(AdminScreen(name='admin_records'))

        return sm

if __name__ == '__main__':
    
    if platform != 'android':  
        Window.size = (600, 800)
    AttendanceApp().run()
