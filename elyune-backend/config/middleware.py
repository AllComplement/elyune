"""
Custom middleware for Elyune backend
"""
import re


class ChromeExtensionCSRFMiddleware:
    """
    Middleware to exempt Chrome extension requests from CSRF validation.
    
    Since we use JWT authentication for the Chrome extension, we don't need
    CSRF protection for those requests. This middleware checks if the request
    origin is a Chrome extension and sets the CSRF cookie accordingly.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.chrome_extension_pattern = re.compile(r'^chrome-extension://[a-z]+$')
    
    def __call__(self, request):
        origin = request.META.get('HTTP_ORIGIN', '')
        
        # If request is from a Chrome extension, mark it as CSRF exempt
        if self.chrome_extension_pattern.match(origin):
            setattr(request, '_dont_enforce_csrf_checks', True)
        
        response = self.get_response(request)
        return response
