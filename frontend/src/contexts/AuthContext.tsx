import React, { createContext, useContext, useState, useCallback } from 'react';
import { login as apiLogin, register as apiRegister } from '../api/auth';
import type { LoginRequest, RegisterRequest, UserResponse } from '../types';

interface AuthState {
  user: UserResponse | null;
  token: string | null;
}

interface AuthContextValue extends AuthState {
  login: (payload: LoginRequest) => Promise<void>;
  register: (payload: RegisterRequest) => Promise<UserResponse>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function loadToken(): string | null {
  return localStorage.getItem('access_token');
}

function loadUser(): UserResponse | null {
  const raw = localStorage.getItem('user');
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserResponse;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: loadToken(),
    user: loadUser(),
  });

  const login = useCallback(async (payload: LoginRequest) => {
    const tokenRes = await apiLogin(payload);
    localStorage.setItem('access_token', tokenRes.access_token);
    // Decode the JWT subject (user id) to use as a minimal user object.
    // The backend does not expose a /me endpoint, so we store the username.
    const minimalUser: UserResponse = {
      id: '',
      username: payload.username,
      email: '',
      is_active: true,
    };
    localStorage.setItem('user', JSON.stringify(minimalUser));
    setState({ token: tokenRes.access_token, user: minimalUser });
  }, []);

  const register = useCallback(async (payload: RegisterRequest) => {
    const user = await apiRegister(payload);
    return user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    setState({ token: null, user: null });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        isAuthenticated: state.token !== null,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
