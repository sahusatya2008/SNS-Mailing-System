import qrcode
import pyzbar.pyzbar as pyzbar
import cv2
import numpy as np
from io import BytesIO
import base64
import logging

class QRScanner:
    """QR Code scanner and generator for SNS Mail"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_qr_code(self, email, size=200):
        """
        Generate QR code for a user's email address
        
        Args:
            email (str): User's email address
            size (int): Size of the QR code image
        
        Returns:
            str: Base64 encoded QR code image
        """
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(email)
            qr.make(fit=True)
            
            # Create image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            img_str = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_str}"
            
        except Exception as e:
            self.logger.error(f"Error generating QR code: {e}")
            return None
    
    def scan_qr_code_from_image(self, image_path):
        """
        Scan QR code from an image file
        
        Args:
            image_path (str): Path to the image file
        
        Returns:
            dict: Result with success status and data
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return {'success': False, 'error': 'Could not read image file'}
            
            # Decode QR codes
            decoded_objects = pyzbar.decode(image)
            
            if not decoded_objects:
                return {'success': False, 'error': 'No QR code found in image'}
            
            # Get the first QR code found
            qr_data = decoded_objects[0].data.decode('utf-8')
            
            return {
                'success': True,
                'data': qr_data,
                'email': self.extract_email_from_qr(qr_data)
            }
            
        except Exception as e:
            self.logger.error(f"Error scanning QR code from image: {e}")
            return {'success': False, 'error': str(e)}
    
    def scan_qr_code_from_webcam(self):
        """
        Scan QR code from webcam
        
        Returns:
            dict: Result with success status and data
        """
        try:
            # Initialize webcam
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                return {'success': False, 'error': 'Could not open webcam'}
            
            qr_found = False
            qr_data = None
            
            while not qr_found:
                # Capture frame-by-frame
                ret, frame = cap.read()
                
                if not ret:
                    break
                
                # Decode QR codes
                decoded_objects = pyzbar.decode(frame)
                
                # Draw bounding box around QR codes
                for obj in decoded_objects:
                    # Draw rectangle
                    points = obj.polygon
                    if len(points) > 4:
                        hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                        points = hull
                    
                    n = len(points)
                    for j in range(0, n):
                        cv2.line(frame, tuple(points[j]), tuple(points[(j+1) % n]), (255, 0, 0), 3)
                    
                    # Display QR code data
                    qr_data = obj.data.decode('utf-8')
                    qr_found = True
                    break
                
                # Display the frame
                cv2.imshow('QR Code Scanner', frame)
                
                # Break on 'q' key press
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            # Release webcam
            cap.release()
            cv2.destroyAllWindows()
            
            if qr_found and qr_data:
                return {
                    'success': True,
                    'data': qr_data,
                    'email': self.extract_email_from_qr(qr_data)
                }
            else:
                return {'success': False, 'error': 'No QR code found'}
                
        except Exception as e:
            self.logger.error(f"Error scanning QR code from webcam: {e}")
            return {'success': False, 'error': str(e)}
    
    def scan_qr_code(self, qr_code_data):
        """
        Scan QR code from provided data (for API usage)
        
        Args:
            qr_code_data (str): QR code data string
        
        Returns:
            dict: Result with success status and email
        """
        try:
            email = self.extract_email_from_qr(qr_code_data)
            
            if email:
                return {
                    'success': True,
                    'data': qr_code_data,
                    'email': email
                }
            else:
                return {'success': False, 'error': 'Invalid QR code data'}
                
        except Exception as e:
            self.logger.error(f"Error processing QR code data: {e}")
            return {'success': False, 'error': str(e)}
    
    def extract_email_from_qr(self, qr_data):
        """
        Extract email from QR code data
        
        Args:
            qr_data (str): QR code data string
        
        Returns:
            str: Extracted email or None
        """
        try:
            # For SNS Mail, QR codes contain just the email address
            # Validate that it's a proper email format
            if '@snsx.com' in qr_data and '.' in qr_data.split('@')[0]:
                return qr_data.strip()
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Error extracting email from QR data: {e}")
            return None
    
    def validate_qr_code(self, qr_data):
        """
        Validate QR code data format
        
        Args:
            qr_data (str): QR code data string
        
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            email = self.extract_email_from_qr(qr_data)
            return email is not None
            
        except Exception as e:
            self.logger.error(f"Error validating QR code: {e}")
            return False
    
    def create_qr_code_from_camera(self):
        """
        Create QR code by capturing from camera (for user registration)
        
        Returns:
            dict: Result with success status and data
        """
        try:
            # This would be used for capturing user's face/eye scan
            # For now, just return a placeholder
            return {
                'success': True,
                'message': 'Camera capture functionality would be implemented here'
            }
            
        except Exception as e:
            self.logger.error(f"Error creating QR code from camera: {e}")
            return {'success': False, 'error': str(e)}