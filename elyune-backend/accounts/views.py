from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import SignupSerializer, LoginSerializer, UserSerializer


@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    User registration endpoint

    Request body:
    {
        "username": "newuser",
        "email": "user@example.com",
        "password": "securepassword123",
        "password2": "securepassword123",
        "first_name": "John",  # Optional
        "last_name": "Doe"     # Optional
    }

    Response:
    {
        "message": "User created successfully",
        "user": {
            "id": 1,
            "username": "newuser",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe"
        },
        "tokens": {
            "refresh": "refresh_token_here",
            "access": "access_token_here"
        }
    }
    """
    serializer = SignupSerializer(data=request.data)

    if serializer.is_valid():
        user = serializer.save()

        # Generate JWT tokens for the new user
        refresh = RefreshToken.for_user(user)

        return Response({
            'message': 'User created successfully',
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint

    Request body:
    {
        "username": "existinguser",
        "password": "userpassword123"
    }

    Response:
    {
        "message": "Login successful",
        "user": {
            "id": 1,
            "username": "existinguser",
            "email": "user@example.com",
            "first_name": "John",
            "last_name": "Doe"
        },
        "tokens": {
            "refresh": "refresh_token_here",
            "access": "access_token_here"
        }
    }
    """
    serializer = LoginSerializer(data=request.data)

    if serializer.is_valid():
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        # Authenticate user
        user = authenticate(username=username, password=password)

        if user is not None:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user).data,
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': 'Invalid username or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
