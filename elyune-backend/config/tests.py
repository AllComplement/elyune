"""
Tests for custom middleware
"""
from django.test import TestCase, RequestFactory
from django.http import HttpResponse
from config.middleware import ChromeExtensionCSRFMiddleware


class ChromeExtensionCSRFMiddlewareTest(TestCase):
    """Test ChromeExtensionCSRFMiddleware functionality"""
    
    def setUp(self):
        self.factory = RequestFactory()
        
        def dummy_get_response(request):
            return HttpResponse("OK")
        
        self.middleware = ChromeExtensionCSRFMiddleware(dummy_get_response)
    
    def test_chrome_extension_origin_bypasses_csrf(self):
        """Test that Chrome extension origins are marked as CSRF exempt"""
        request = self.factory.get('/api/test/')
        request.META['HTTP_ORIGIN'] = 'chrome-extension://aflcfedlpbjfcgmchoedaonmgenbiclg'
        
        self.middleware(request)
        
        # Check that the request is marked as CSRF exempt
        self.assertTrue(hasattr(request, '_dont_enforce_csrf_checks'))
        self.assertTrue(request._dont_enforce_csrf_checks)
    
    def test_regular_origin_not_bypassed(self):
        """Test that regular HTTP origins are not marked as CSRF exempt"""
        request = self.factory.get('/api/test/')
        request.META['HTTP_ORIGIN'] = 'http://localhost:3000'
        
        self.middleware(request)
        
        # Check that the request is NOT marked as CSRF exempt
        self.assertFalse(hasattr(request, '_dont_enforce_csrf_checks') and 
                         request._dont_enforce_csrf_checks)
    
    def test_no_origin_not_bypassed(self):
        """Test that requests without origin are not marked as CSRF exempt"""
        request = self.factory.get('/api/test/')
        
        self.middleware(request)
        
        # Check that the request is NOT marked as CSRF exempt
        self.assertFalse(hasattr(request, '_dont_enforce_csrf_checks') and 
                         request._dont_enforce_csrf_checks)
    
    def test_invalid_chrome_extension_not_bypassed(self):
        """Test that invalid chrome-extension URIs are not bypassed"""
        request = self.factory.get('/api/test/')
        request.META['HTTP_ORIGIN'] = 'chrome-extension://invalid123/path'
        
        self.middleware(request)
        
        # Check that the request is NOT marked as CSRF exempt
        self.assertFalse(hasattr(request, '_dont_enforce_csrf_checks') and 
                         request._dont_enforce_csrf_checks)
