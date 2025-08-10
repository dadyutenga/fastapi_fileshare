# FastAPI File Sharing Backend - API Documentation

## Base URL
```
http://your-server-domain.com
```

## Authentication
The API uses JWT Bearer token authentication. Include the token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

---

## 🔐 Authentication Endpoints

### 1. Register User (API)
**Endpoint:** `POST /auth/register`  
**Content-Type:** `application/x-www-form-urlencoded`  
**Authentication:** None required

**Request Body (Form Data):**
```
username=your_username
password=your_password
```

**Flutter Example:**
```dart
import 'package:http/http.dart' as http;

Future<Map<String, dynamic>> registerUser(String username, String password) async {
  final response = await http.post(
    Uri.parse('$baseUrl/auth/register'),
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: {
      'username': username,
      'password': password,
    },
  );
  
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Registration failed: ${response.body}');
  }
}
```

**Response (Success):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Response (Error):**
```json
{
  "detail": "Username already registered"
}
```

**Validation Rules:**
- Username: Required, unique
- Password: Minimum 6 characters

---

### 2. Login User (API)
**Endpoint:** `POST /auth/login`  
**Content-Type:** `application/x-www-form-urlencoded`  
**Authentication:** None required

**Request Body (Form Data):**
```
username=your_username
password=your_password
```

**Flutter Example:**
```dart
Future<Map<String, dynamic>> loginUser(String username, String password) async {
  final response = await http.post(
    Uri.parse('$baseUrl/auth/login'),
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: {
      'username': username,
      'password': password,
    },
  );
  
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Login failed: ${response.body}');
  }
}
```

**Response (Success):**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer"
}
```

**Response (Error):**
```json
{
  "detail": "Incorrect username or password"
}
```

---

### 3. Logout
**Endpoint:** `POST /auth/logout`  
**Authentication:** Required

**Flutter Example:**
```dart
Future<void> logoutUser(String token) async {
  final response = await http.post(
    Uri.parse('$baseUrl/auth/logout'),
    headers: {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    },
  );
  
  if (response.statusCode != 200) {
    throw Exception('Logout failed');
  }
}
```

**Response:**
```json
{
  "message": "Successfully logged out"
}
```

---

## 📁 File Management Endpoints

### 4. Upload File (Small Files - Up to 50MB)
**Endpoint:** `POST /files/upload-api`  
**Content-Type:** `multipart/form-data`  
**Authentication:** Required

**Request Body (Form Data):**
```
file: File (required)
ttl: integer (optional, default: 0) - Expiry time in hours (0 = no expiry)
is_public: string (optional, default: "false") - "true" or "false"
```

**Flutter Example:**
```dart
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'dart:io';

Future<Map<String, dynamic>> uploadFile(
  File file, 
  String token, 
  {int ttl = 0, bool isPublic = false}
) async {
  var request = http.MultipartRequest(
    'POST', 
    Uri.parse('$baseUrl/files/upload-api')
  );
  
  // Add headers
  request.headers['Authorization'] = 'Bearer $token';
  
  // Add file
  request.files.add(await http.MultipartFile.fromPath(
    'file',
    file.path,
    contentType: MediaType('application', 'octet-stream'),
  ));
  
  // Add form fields
  request.fields['ttl'] = ttl.toString();
  request.fields['is_public'] = isPublic.toString();
  
  var response = await request.send();
  var responseBody = await response.stream.bytesToString();
  
  if (response.statusCode == 200) {
    return json.decode(responseBody);
  } else {
    throw Exception('Upload failed: $responseBody');
  }
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "File uploaded successfully",
  "file_id": "abc123def456",
  "download_url": "http://domain.com/files/download/abc123def456",
  "preview_url": "http://domain.com/files/preview/abc123def456",
  "filename": "document.pdf",
  "file_size": 1048576,
  "is_public": false
}
```

---

### 5. Chunked Upload (Large Files - 50MB to 500MB)

#### 5.1. Start Chunked Upload
**Endpoint:** `POST /files/chunked-upload/start`  
**Content-Type:** `application/x-www-form-urlencoded`  
**Authentication:** Required

**Request Body (Form Data):**
```
filename=large_video.mp4
file_size=104857600
total_chunks=50
ttl=0
is_public=false
```

#### 5.2. Upload Chunk
**Endpoint:** `POST /files/chunked-upload/chunk`  
**Content-Type:** `multipart/form-data`  
**Authentication:** Required

#### 5.3. Complete Chunked Upload
**Endpoint:** `POST /files/chunked-upload/complete`  
**Content-Type:** `application/x-www-form-urlencoded`  
**Authentication:** Required

#### 5.4. Cancel Chunked Upload
**Endpoint:** `DELETE /files/chunked-upload/cancel`  
**Content-Type:** `application/x-www-form-urlencoded`  
**Authentication:** Required

---

### 6. Download File
**Endpoint:** `GET /files/download/{file_id}`  
**Authentication:** Required for private files, Optional for public files

**Flutter Example:**
```dart
Future<List<int>> downloadFile(String fileId, String? token) async {
  Map<String, String> headers = {};
  if (token != null) {
    headers['Authorization'] = 'Bearer $token';
  }
  
  final response = await http.get(
    Uri.parse('$baseUrl/files/download/$fileId'),
    headers: headers,
  );
  
  if (response.statusCode == 200) {
    return response.bodyBytes;
  } else {
    throw Exception('Download failed: ${response.body}');
  }
}
```

---

### 7. Get File Preview (JSON)
**Endpoint:** `GET /files/api/preview/{file_id}`  
**Authentication:** Required for private files, Optional for public files

**Flutter Example:**
```dart
Future<Map<String, dynamic>> getFilePreview(String fileId, String? token) async {
  Map<String, String> headers = {};
  if (token != null) {
    headers['Authorization'] = 'Bearer $token';
  }
  
  final response = await http.get(
    Uri.parse('$baseUrl/files/api/preview/$fileId'),
    headers: headers,
  );
  
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to get preview: ${response.body}');
  }
}
```

---

### 8. Delete File
**Endpoint:** `POST /files/delete/{file_id}`  
**Authentication:** Required (Owner only)

---

### 9. Toggle File Privacy
**Endpoint:** `POST /files/toggle-privacy/{file_id}`  
**Authentication:** Required (Owner only)

---

### 10. Delete All User Files
**Endpoint:** `POST /files/delete-all`  
**Authentication:** Required

---

## 📊 User Dashboard Endpoints (HTML Pages)

### 11. Home Page
**Endpoint:** `GET /`  
**Authentication:** Optional  
**Response:** HTML page

### 12. Login Page
**Endpoint:** `GET /login`  
**Authentication:** None  
**Response:** HTML page

### 13. Register Page
**Endpoint:** `GET /register`  
**Authentication:** None  
**Response:** HTML page

### 14. User Dashboard
**Endpoint:** `GET /dashboard`  
**Authentication:** Required  
**Response:** HTML page with user statistics

### 15. User Files Page
**Endpoint:** `GET /files`  
**Authentication:** Required  
**Response:** HTML page with user's files list

### 16. File Preview Page
**Endpoint:** `GET /files/preview/{file_id}`  
**Authentication:** Required for private files, Optional for public files  
**Response:** HTML page with file preview

### 17. Logout
**Endpoint:** `GET /logout`  
**Authentication:** Required  
**Response:** Redirect to home page