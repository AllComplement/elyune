import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { RecordingScreen } from './components/RecordingScreen';
import { LoginScreen } from './components/LoginScreen';
import { SignupScreen } from './components/SignupScreen';
import { SettingsScreen } from './components/SettingsScreen';
import { AuthProvider, useAuth } from './hooks/useAuth';
import './App.css';

function AppRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  // Show loading state while initializing
  if (isLoading) {
    return (
      <div className="popup-container">
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <Routes>
      {/* Public routes */}
      <Route path="/settings" element={<SettingsScreen />} />
      <Route
        path="/login"
        element={
          isAuthenticated ? <Navigate to="/" replace /> : <LoginScreen />
        }
      />
      <Route
        path="/signup"
        element={
          isAuthenticated ? <Navigate to="/" replace /> : <SignupScreen />
        }
      />

      {/* Protected routes */}
      <Route
        path="/"
        element={
          isAuthenticated ? <RecordingScreen /> : <Navigate to="/login" replace />
        }
      />

      {/* Catch all - redirect to home */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
