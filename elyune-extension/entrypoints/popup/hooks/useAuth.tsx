import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { User } from '../types/api.types';
import { getAuthState, setAuthState as saveAuthState, clearAuthState as removeAuthState, initializeStorage } from '../services/storage';
import { apiClient } from '../services/api';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: User | null;
  login: (authToken: string, refreshToken: string, user: User) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  // Initialize on mount
  useEffect(() => {
    const initialize = async () => {
      try {
        await initializeStorage();
        const authState = await getAuthState();

        setIsAuthenticated(authState.isAuthenticated);
        setUser(authState.user);

        // Initialize API client
        if (authState.isAuthenticated && authState.authToken && authState.refreshToken) {
          apiClient.setAuthTokens(authState.authToken, authState.refreshToken);
        }
      } catch (error) {
        console.error('Failed to initialize auth:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initialize();
  }, []);

  const login = async (authToken: string, refreshToken: string, user: User) => {
    await saveAuthState(authToken, refreshToken, user);
    apiClient.setAuthTokens(authToken, refreshToken);
    setIsAuthenticated(true);
    setUser(user);
  };

  const logout = async () => {
    await removeAuthState();
    apiClient.setAuthTokens(null, null);
    setIsAuthenticated(false);
    setUser(null);
  };

  const updateUser = (updatedUser: User) => {
    setUser(updatedUser);
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading,
        user,
        login,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
