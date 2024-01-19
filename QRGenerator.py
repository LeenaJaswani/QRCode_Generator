import tkinter as tk
from tkinter import ttk, messagebox
import qrcode
import snowflake.connector
from PIL import Image, ImageTk
from io import BytesIO
import os
from ibm_botocore.client import Config

import ibm_boto3
import configparser
config = configparser.ConfigParser()
config.read('config.ini')


cos_api_key_id = config.get('IBM_COS', 'api_key_id')
cos_service_instance_id = config.get('IBM_COS', 'service_instance_id')
cos_auth_endpoint = config.get('IBM_COS', 'auth_endpoint')
cos_endpoint = config.get('IBM_COS', 'endpoint')
cos_bucket_name = config.get('IBM_COS', 'bucket_name')
cos_bucket_location=config.get('IBM_COS', 'bucket_location')


cos_client = ibm_boto3.client('s3',
    ibm_api_key_id=cos_api_key_id,
    ibm_service_instance_id=cos_service_instance_id,
    ibm_auth_endpoint=cos_auth_endpoint,
    config=Config(signature_version='oauth'),
    endpoint_url=cos_endpoint
)
snowflake_user = config.get('SNOWFLAKE', 'user')
snowflake_password = config.get('SNOWFLAKE', 'password')
snowflake_account = config.get('SNOWFLAKE', 'account')
snowflake_warehouse = config.get('SNOWFLAKE', 'warehouse')
snowflake_database = config.get('SNOWFLAKE', 'database')
snowflake_schema = config.get('SNOWFLAKE', 'schema')
# Function to upload file to IBM Cloud Object Storage
def upload_to_cos(file_path, object_name):
    try:
        with open(file_path, 'rb') as data:
            cos_client.upload_fileobj(data, cos_bucket_name, object_name)
        print(f"File uploaded successfully: {object_name}")
    except Exception as e:
        print(f"Error uploading file to COS: {e}")




def generate_qr_code():
    employee_id = entry_employee_id.get()
    employee_name = entry_employee_name.get()

    if not employee_id or not is_valid_employee_name(employee_name) or contains_special_characters(employee_id):
        messagebox.showerror("Error", "Please enter a valid Employee ID and Name. Employee ID and Employee Name cannot contain special characters, and Name cannot contain numbers or special characters.")
        return

    # Check if the Employee ID already exists in the database
    if employee_exists(employee_id):
        
        response = messagebox.askquestion("Employee Exists", "Employee ID already exists. Do you want to regenerate the QR code?")
        if response == "no":
            return

   
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=4,
        border=2,
    )
    qr.add_data(f"Employee ID: {employee_id}\nEmployee Name: {employee_name}")
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

   
    filename = f"{employee_id}_{employee_name.replace(' ', '_')}.png"

   
    save_employee_details(employee_id, employee_name, img, filename)

 
    folder_path = os.path.join(script_dir, 'image', 'qrcode')
    os.makedirs(folder_path, exist_ok=True)

    
    img.save(os.path.join(folder_path, filename))

    upload_to_cos(os.path.join(folder_path, filename), filename)

    img_tk = ImageTk.PhotoImage(img)

    label_qr_code.configure(image=img_tk)
    label_qr_code.image = img_tk

    messagebox.showinfo("Success", "Employee Qr saved successfully.")


def contains_special_characters(s):
    return not s.isalnum()

def employee_exists(employee_id):
    conn = snowflake.connector.connect(
       user=snowflake_user,
        password=snowflake_password,
        account=snowflake_account,
        warehouse=snowflake_warehouse,
        database=snowflake_database,
        schema=snowflake_schema
    )
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM employees WHERE employee_id = %s", (employee_id,))
    result = cursor.fetchone()

    conn.close()

    return result is not None

def save_employee_details(employee_id, employee_name, img, filename):
    try:
        # Connect to the Snowflake database
        conn = snowflake.connector.connect(
           user=snowflake_user,
        password=snowflake_password,
        account=snowflake_account,
        warehouse=snowflake_warehouse,
        database=snowflake_database,
        schema=snowflake_schema
        )

        cursor = conn.cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS employees
                          (employee_id VARCHAR(36) PRIMARY KEY, 
                           employee_name VARCHAR(255), 
                           qr_code_image BINARY, 
                           image_url VARCHAR(255), 
                           filename VARCHAR(255))''')

        # existing_filename = cursor.execute("SELECT filename FROM employees WHERE employee_id = %s", (employee_id,)).fetchone()

        img_bytes = BytesIO()
        img.save(img_bytes)
        img_bytes = img_bytes.getvalue()

        
     
        image_url = f"https://{cos_bucket_name}.{cos_bucket_location}/{filename}"

        if employee_exists(employee_id):
           
            cursor.execute("UPDATE employees SET employee_name = %s, qr_code_image = %s, image_url = %s, filename = %s WHERE employee_id = %s",
                           (employee_name, img_bytes, image_url, filename, employee_id))
        else:
           
            cursor.execute("INSERT INTO employees (employee_id, employee_name, qr_code_image, image_url, filename) VALUES (%s, %s, %s, %s, %s)",
                           (employee_id, employee_name, img_bytes, image_url, filename))

        conn.commit()
    except snowflake.connector.errors.ProgrammingError as err:
        messagebox.showerror("Error", f"Error: {err}")
    except Exception as e:
        messagebox.showerror("Error", f"An error occurred: {e}")
    finally:
        
        try:
            if conn and not conn.is_closed():
                conn.close()
        except Exception as e:
            print(f"Error closing connection: {e}")

def is_valid_employee_name(name):
    return all(char.isalpha() or char.isspace() for char in name)



root = tk.Tk()
root.title("QR Code Generator")
script_dir = os.path.dirname(os.path.abspath(__file__))
image_dir = os.path.join(script_dir, 'image')
icon_image_path = os.path.join(image_dir, 'qr-code.png')
icon_image = Image.open(icon_image_path)
# icon_image = Image.open("image/qr-code.png")  
icon_photo = ImageTk.PhotoImage(icon_image)
root.iconphoto(False, icon_photo)
# Stylish color scheme
background_color = "#a2d6f9"
label_color = "#393d3f"
entry_color = "#edf2f4"
button_color = "#f9c22e"

root.configure(bg=background_color)

user_image_path = os.path.join(image_dir, 'user.png')
image = Image.open(user_image_path)

# image = Image.open("image/user.png")  
photo = ImageTk.PhotoImage(image)
label_image = tk.Label(root, image=photo, bg=background_color)
label_image.grid(row=0, column=0, columnspan=5, pady=(10, 20), sticky="nsew")

style = ttk.Style()
style.configure('TFrame', background=background_color) 
frame = ttk.Frame(root, padding=20, style='TFrame')
frame.grid(row=1, column=0, columnspan=5, pady=(10, 20), sticky="nsew")

frame.grid_columnconfigure(0, weight=1)
frame.grid_columnconfigure(1, weight=1)

frame.grid_rowconfigure(0, weight=1)
frame.grid_rowconfigure(1, weight=1)
frame.grid_rowconfigure(2, weight=1)

label_employee_id = ttk.Label(frame, text="Employee ID:", background=background_color, font=('Arial', 12, 'bold'), foreground=label_color)
label_employee_id.grid(row=0, column=0, padx=10, pady=10, sticky=tk.E)

entry_employee_id = ttk.Entry(frame, style='TEntry', font=('Arial', 11), background=entry_color)
entry_employee_id.grid(row=0, column=1, padx=10, pady=10, sticky=tk.W)

label_employee_name = ttk.Label(frame, text="Employee Name:", background=background_color, font=('Arial', 12, 'bold'), foreground=label_color)
label_employee_name.grid(row=1, column=0, padx=10, pady=10, sticky=tk.E)

entry_employee_name = ttk.Entry(frame, style='TEntry', font=('Arial', 11), background=entry_color)
entry_employee_name.grid(row=1, column=1, padx=10, pady=10, sticky=tk.W)

button_generate_qr = ttk.Button(frame, text="Generate QR Code", command=generate_qr_code, style='TButton')
button_generate_qr.grid(row=2, column=0, columnspan=2, pady=20)

label_qr_code = tk.Label(root, bg=background_color)
label_qr_code.grid(row=2, column=0, columnspan=5, pady=(10, 20), sticky="nsew")


for i in range(5):
    root.grid_rowconfigure(i, weight=1)

for i in range(5):
    root.grid_columnconfigure(i, weight=1)

root.mainloop()
