# 📱 User Files API Documentation for Flutter/Dio

## Overview
This documentation covers the `/api/user-files` endpoint for retrieving user files with filtering, pagination, and search capabilities. Perfect for mobile app integration with Flutter and Dio.

---

## 🔐 Authentication Required
All requests to this endpoint require a valid Bearer token obtained from the login endpoint.

---

## 📍 Endpoint Details

### Get User Files
**Endpoint:** `GET /files/api/user-files`  
**Authentication:** Required (Bearer Token)  
**Description:** Retrieve paginated list of user's files with optional filtering and search

---

## 📊 Request Parameters

### Query Parameters (All Optional)

| Parameter | Type | Default | Range/Options | Description |
|-----------|------|---------|---------------|-------------|
| `limit` | int | 100 | 1-500 | Number of files per page |
| `offset` | int | 0 | ≥ 0 | Number of files to skip (for pagination) |
| `file_type` | string | null | `image`, `video`, `document`, `audio` | Filter by file category |
| `search_query` | string | null | Any text | Search in filenames (case-insensitive) |

### Example URLs:
```
GET /files/api/user-files
GET /files/api/user-files?limit=20&offset=0
GET /files/api/user-files?file_type=image
GET /files/api/user-files?search_query=report
GET /files/api/user-files?limit=50&file_type=video&search_query=vacation
```

---

## 📱 Flutter/Dio Implementation

### 1. Setup Dio Client

```dart
import 'package:dio/dio.dart';

class ApiService {
  late Dio _dio;
  final String baseUrl = 'http://your-server:8001'; // Replace with your server URL
  
  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: Duration(seconds: 10),
      receiveTimeout: Duration(seconds: 10),
      headers: {
        'Content-Type': 'application/json',
      },
    ));
    
    // Add token interceptor
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) {
        // Add token to all requests
        final token = getStoredToken(); // Your token storage method
        if (token != null) {
          options.headers['Authorization'] = 'Bearer $token';
        }
        handler.next(options);
      },
    ));
  }
  
  String? getStoredToken() {
    // Implement your token storage logic (SharedPreferences, etc.)
    return 'your_stored_token';
  }
}
```

### 2. User Files Response Model

```dart
class UserFilesResponse {
  final bool success;
  final List<FileItem> files;
  final Pagination pagination;
  final Filters filters;
  final UserStats userStats;
  final UserInfo userInfo;

  UserFilesResponse({
    required this.success,
    required this.files,
    required this.pagination,
    required this.filters,
    required this.userStats,
    required this.userInfo,
  });

  factory UserFilesResponse.fromJson(Map<String, dynamic> json) {
    return UserFilesResponse(
      success: json['success'] ?? false,
      files: (json['files'] as List?)
          ?.map((file) => FileItem.fromJson(file))
          .toList() ?? [],
      pagination: Pagination.fromJson(json['pagination'] ?? {}),
      filters: Filters.fromJson(json['filters'] ?? {}),
      userStats: UserStats.fromJson(json['user_stats'] ?? {}),
      userInfo: UserInfo.fromJson(json['user_info'] ?? {}),
    );
  }
}

class FileItem {
  final String fileId;
  final String filename;
  final int fileSize;
  final String formattedSize;
  final String? contentType;
  final String fileCategory;
  final bool isPublic;
  final bool isExpired;
  final String? uploadDate;
  final int ttl;
  final String downloadUrl;
  final String previewUrl;
  final String? fileHash;
  final int downloadCount;

  FileItem({
    required this.fileId,
    required this.filename,
    required this.fileSize,
    required this.formattedSize,
    this.contentType,
    required this.fileCategory,
    required this.isPublic,
    required this.isExpired,
    this.uploadDate,
    required this.ttl,
    required this.downloadUrl,
    required this.previewUrl,
    this.fileHash,
    required this.downloadCount,
  });

  factory FileItem.fromJson(Map<String, dynamic> json) {
    return FileItem(
      fileId: json['file_id'] ?? '',
      filename: json['filename'] ?? '',
      fileSize: json['file_size'] ?? 0,
      formattedSize: json['formatted_size'] ?? '0 B',
      contentType: json['content_type'],
      fileCategory: json['file_category'] ?? 'other',
      isPublic: json['is_public'] ?? false,
      isExpired: json['is_expired'] ?? false,
      uploadDate: json['upload_date'],
      ttl: json['ttl'] ?? 0,
      downloadUrl: json['download_url'] ?? '',
      previewUrl: json['preview_url'] ?? '',
      fileHash: json['file_hash'],
      downloadCount: json['download_count'] ?? 0,
    );
  }
}

class Pagination {
  final int totalCount;
  final int limit;
  final int offset;
  final bool hasNext;
  final bool hasPrevious;
  final int currentPage;
  final int totalPages;

  Pagination({
    required this.totalCount,
    required this.limit,
    required this.offset,
    required this.hasNext,
    required this.hasPrevious,
    required this.currentPage,
    required this.totalPages,
  });

  factory Pagination.fromJson(Map<String, dynamic> json) {
    return Pagination(
      totalCount: json['total_count'] ?? 0,
      limit: json['limit'] ?? 100,
      offset: json['offset'] ?? 0,
      hasNext: json['has_next'] ?? false,
      hasPrevious: json['has_previous'] ?? false,
      currentPage: json['current_page'] ?? 1,
      totalPages: json['total_pages'] ?? 1,
    );
  }
}

class Filters {
  final String? fileType;
  final String? searchQuery;

  Filters({this.fileType, this.searchQuery});

  factory Filters.fromJson(Map<String, dynamic> json) {
    return Filters(
      fileType: json['file_type'],
      searchQuery: json['search_query'],
    );
  }
}

class UserStats {
  final int userId;
  final String? username;
  final int storageLimit;
  final String formattedStorageLimit;
  final int storageUsed;
  final String formattedStorageUsed;
  final int storageAvailable;
  final double storagePercentage;
  final int dailyDownloadLimit;
  final String formattedDownloadLimit;
  final int dailyDownloadsUsed;
  final double dailyDownloadPercentage;
  final int totalFiles;
  final int totalDownloads;

  UserStats({
    required this.userId,
    this.username,
    required this.storageLimit,
    required this.formattedStorageLimit,
    required this.storageUsed,
    required this.formattedStorageUsed,
    required this.storageAvailable,
    required this.storagePercentage,
    required this.dailyDownloadLimit,
    required this.formattedDownloadLimit,
    required this.dailyDownloadsUsed,
    required this.dailyDownloadPercentage,
    required this.totalFiles,
    required this.totalDownloads,
  });

  factory UserStats.fromJson(Map<String, dynamic> json) {
    return UserStats(
      userId: json['user_id'] ?? 0,
      username: json['username'],
      storageLimit: json['storage_limit'] ?? 0,
      formattedStorageLimit: json['formatted_storage_limit'] ?? '0 B',
      storageUsed: json['storage_used'] ?? 0,
      formattedStorageUsed: json['formatted_storage_used'] ?? '0 B',
      storageAvailable: json['storage_available'] ?? 0,
      storagePercentage: (json['storage_percentage'] ?? 0.0).toDouble(),
      dailyDownloadLimit: json['daily_download_limit'] ?? 0,
      formattedDownloadLimit: json['formatted_download_limit'] ?? '0 B',
      dailyDownloadsUsed: json['daily_downloads_used'] ?? 0,
      dailyDownloadPercentage: (json['daily_download_percentage'] ?? 0.0).toDouble(),
      totalFiles: json['total_files'] ?? 0,
      totalDownloads: json['total_downloads'] ?? 0,
    );
  }
}

class UserInfo {
  final int userId;
  final String? username;

  UserInfo({required this.userId, this.username});

  factory UserInfo.fromJson(Map<String, dynamic> json) {
    return UserInfo(
      userId: json['user_id'] ?? 0,
      username: json['username'],
    );
  }
}
```

### 3. API Service Methods

```dart
class FileApiService extends ApiService {
  
  // Get user files with optional filtering and pagination
  Future<UserFilesResponse> getUserFiles({
    int limit = 100,
    int offset = 0,
    String? fileType,
    String? searchQuery,
  }) async {
    try {
      final queryParams = <String, dynamic>{
        'limit': limit,
        'offset': offset,
      };
      
      if (fileType != null) queryParams['file_type'] = fileType;
      if (searchQuery != null && searchQuery.isNotEmpty) {
        queryParams['search_query'] = searchQuery;
      }
      
      final response = await _dio.get(
        '/files/api/user-files',
        queryParameters: queryParams,
      );
      
      if (response.statusCode == 200) {
        return UserFilesResponse.fromJson(response.data);
      } else {
        throw Exception('Failed to fetch user files: ${response.statusCode}');
      }
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        throw Exception('Authentication failed. Please login again.');
      } else if (e.response?.statusCode == 500) {
        throw Exception('Server error. Please try again later.');
      } else {
        throw Exception('Network error: ${e.message}');
      }
    } catch (e) {
      throw Exception('Unexpected error: $e');
    }
  }
  
  // Get files by category
  Future<UserFilesResponse> getFilesByCategory(String category, {
    int limit = 100,
    int offset = 0,
  }) async {
    return await getUserFiles(
      limit: limit,
      offset: offset,
      fileType: category,
    );
  }
  
  // Search files
  Future<UserFilesResponse> searchFiles(String query, {
    int limit = 100,
    int offset = 0,
    String? fileType,
  }) async {
    return await getUserFiles(
      limit: limit,
      offset: offset,
      fileType: fileType,
      searchQuery: query,
    );
  }
  
  // Load next page
  Future<UserFilesResponse> loadNextPage(UserFilesResponse currentResponse) async {
    if (!currentResponse.pagination.hasNext) {
      return currentResponse; // No more pages
    }
    
    return await getUserFiles(
      limit: currentResponse.pagination.limit,
      offset: currentResponse.pagination.offset + currentResponse.pagination.limit,
    );
  }
}
```

### 4. Usage Examples

#### Basic Usage
```dart
final fileService = FileApiService();

// Get first 20 files
try {
  final response = await fileService.getUserFiles(limit: 20);
  print('Total files: ${response.pagination.totalCount}');
  print('Storage used: ${response.userStats.formattedStorageUsed}');
  
  for (final file in response.files) {
    print('File: ${file.filename} (${file.formattedSize})');
  }
} catch (e) {
  print('Error: $e');
}
```

#### Filter by File Type
```dart
// Get only images
final imageFiles = await fileService.getFilesByCategory('image');

// Get only documents
final documentFiles = await fileService.getFilesByCategory('document');

// Get only videos
final videoFiles = await fileService.getFilesByCategory('video');

// Get only audio files
final audioFiles = await fileService.getFilesByCategory('audio');
```

#### Search Files
```dart
// Search for files containing "report"
final searchResults = await fileService.searchFiles('report');

// Search for images containing "vacation"
final vacationImages = await fileService.searchFiles(
  'vacation',
  fileType: 'image',
);
```

#### Pagination Example
```dart
class FilesController {
  List<FileItem> _allFiles = [];
  UserFilesResponse? _lastResponse;
  bool _isLoading = false;
  
  Future<void> loadInitialFiles() async {
    _isLoading = true;
    try {
      _lastResponse = await fileService.getUserFiles(limit: 20);
      _allFiles = _lastResponse!.files;
    } catch (e) {
      print('Error loading files: $e');
    } finally {
      _isLoading = false;
    }
  }
  
  Future<void> loadMoreFiles() async {
    if (_isLoading || _lastResponse == null || !_lastResponse!.pagination.hasNext) {
      return;
    }
    
    _isLoading = true;
    try {
      final response = await fileService.loadNextPage(_lastResponse!);
      _allFiles.addAll(response.files);
      _lastResponse = response;
    } catch (e) {
      print('Error loading more files: $e');
    } finally {
      _isLoading = false;
    }
  }
}
```

---

## 📋 Response Examples

### Success Response
```json
{
  "success": true,
  "files": [
    {
      "file_id": "abc123def456",
      "filename": "vacation_photo.jpg",
      "file_size": 2048576,
      "formatted_size": "2.0 MB",
      "content_type": "image/jpeg",
      "file_category": "image",
      "is_public": false,
      "is_expired": false,
      "upload_date": "2025-08-11T10:30:00",
      "ttl": 0,
      "download_url": "/api/files/download/abc123def456",
      "preview_url": "/api/files/preview/abc123def456",
      "file_hash": "sha256_hash_here",
      "download_count": 5
    }
  ],
  "pagination": {
    "total_count": 150,
    "limit": 20,
    "offset": 0,
    "has_next": true,
    "has_previous": false,
    "current_page": 1,
    "total_pages": 8
  },
  "filters": {
    "file_type": null,
    "search_query": null
  },
  "user_stats": {
    "user_id": 1,
    "username": "john_doe",
    "storage_limit": 5368709120,
    "formatted_storage_limit": "5.0 GB",
    "storage_used": 157286400,
    "formatted_storage_used": "150.0 MB",
    "storage_available": 5211422720,
    "storage_percentage": 2.93,
    "daily_download_limit": 1073741824,
    "formatted_download_limit": "1.0 GB",
    "daily_downloads_used": 52428800,
    "daily_download_percentage": 4.88,
    "total_files": 25,
    "total_downloads": 125
  },
  "user_info": {
    "user_id": 1,
    "username": "john_doe"
  }
}
```

### Error Response
```json
{
  "detail": "Authentication failed"
}
```

---

## 🎨 File Categories

The API automatically categorizes files into these types:

- **`image`**: jpg, jpeg, png, gif, bmp, webp, svg
- **`video`**: mp4, avi, mkv, mov, wmv, flv, webm
- **`document`**: pdf, doc, docx, xls, xlsx, txt
- **`audio`**: mp3, wav, aac, ogg, flac
- **`other`**: All other file types

---

## 🚀 Best Practices

### 1. Error Handling
```dart
try {
  final files = await fileService.getUserFiles();
  // Handle success
} on Exception catch (e) {
  if (e.toString().contains('Authentication failed')) {
    // Redirect to login
  } else if (e.toString().contains('Network error')) {
    // Show retry option
  } else {
    // Show generic error
  }
}
```

### 2. Pagination Strategy
- Start with limit=20 for mobile screens
- Load more when user scrolls to bottom
- Show loading indicators during requests

### 3. Caching
- Cache file lists locally using SharedPreferences or SQLite
- Refresh cache when user pulls to refresh
- Cache user stats for offline viewing

### 4. UI Considerations
- Show file category icons based on `file_category`
- Display `formatted_size` instead of raw bytes
- Use `storage_percentage` for progress bars
- Show upload date in user's timezone

---

## 🔧 Testing with cURL

```bash
# Basic request
curl -X GET "http://localhost:8001/files/api/user-files" \
  -H "Authorization: Bearer your_token_here"

# With pagination
curl -X GET "http://localhost:8001/files/api/user-files?limit=10&offset=0" \
  -H "Authorization: Bearer your_token_here"

# Filter by file type
curl -X GET "http://localhost:8001/files/api/user-files?file_type=image" \
  -H "Authorization: Bearer your_token_here"

# Search files
curl -X GET "http://localhost:8001/files/api/user-files?search_query=report" \
  -H "Authorization: Bearer your_token_here"
```

---

## 📱 Mobile UI Integration Tips

### ListView with Pagination
```dart
class FilesListView extends StatefulWidget {
  @override
  _FilesListViewState createState() => _FilesListViewState();
}

class _FilesListViewState extends State<FilesListView> {
  final ScrollController _scrollController = ScrollController();
  final FilesController _filesController = FilesController();
  
  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _filesController.loadInitialFiles();
  }
  
  void _onScroll() {
    if (_scrollController.position.pixels == 
        _scrollController.position.maxScrollExtent) {
      _filesController.loadMoreFiles();
    }
  }
  
  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      controller: _scrollController,
      itemCount: _filesController.files.length,
      itemBuilder: (context, index) {
        final file = _filesController.files[index];
        return FileListTile(file: file);
      },
    );
  }
}
```

Good luck with your Android app implementation! 🚀📱