# Test API

Test the Elyune backend API endpoints using curl commands.

## Instructions

When this command is invoked, test the authentication and API endpoints in the following order:

### 1. Test Signup Endpoint

Create a new user with a timestamp-based username:

```bash
TIMESTAMP=$(date +%s)
USERNAME="testuser_$TIMESTAMP"

curl -s -X POST http://localhost:8000/api/auth/signup/ \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"$USERNAME\",
    \"email\": \"${USERNAME}@example.com\",
    \"password\": \"SecurePass123\",
    \"password2\": \"SecurePass123\",
    \"first_name\": \"Test\",
    \"last_name\": \"User\"
  }" | python3 -m json.tool
```

Save the access token from the response for later tests.

### 2. Test Login Endpoint

Login with the created user:

```bash
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"$USERNAME\",
    \"password\": \"SecurePass123\"
  }" | python3 -m json.tool
```

### 3. Test Token Refresh

Extract the refresh token from login response and test refresh:

```bash
REFRESH_TOKEN="<refresh_token_from_login>"

curl -s -X POST http://localhost:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d "{\"refresh\": \"$REFRESH_TOKEN\"}" | python3 -m json.tool
```

### 4. Test Protected Endpoint

Use the access token to fetch recordings:

```bash
ACCESS_TOKEN="<access_token_from_login>"

curl -s http://localhost:8000/api/v1/recordings/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python3 -m json.tool
```

### 5. Test Upload Request

Request a presigned upload URL:

```bash
curl -s -X POST http://localhost:8000/api/v1/recordings/request-upload/ \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "test-recording.webm",
    "file_size": 10485760,
    "quality": "1080p",
    "fps": 30,
    "has_system_audio": true,
    "has_microphone": false
  }' | python3 -m json.tool
```

### 6. Test Invalid Login

Verify error handling with wrong credentials:

```bash
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "nonexistent",
    "password": "wrongpassword"
  }' | python3 -m json.tool
```

## Expected Results

- ✓ Signup should return user data and JWT tokens
- ✓ Login should return user data and JWT tokens
- ✓ Token refresh should return new access token
- ✓ Protected endpoint should return recordings list (empty array initially)
- ✓ Upload request should return recording_id, upload_url, and s3_key
- ✓ Invalid login should return error: "Invalid username or password"

## Notes

- All endpoints except signup/login require JWT authentication
- Tokens are saved between requests for convenience
- Use the access token in Authorization header: `Bearer <token>`
- Access tokens expire after 1 hour
- Refresh tokens expire after 7 days
- Backend must be running: `cd elyune-backend && docker compose up -d`
