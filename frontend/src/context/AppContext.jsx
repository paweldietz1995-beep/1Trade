import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL + '/api';

const AppContext = createContext(null);

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within AppProvider');
  }
  return context;
};

export const AppProvider = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState(localStorage.getItem('auth_token'));
  const [loading, setLoading] = useState(true);

  // Verify token on mount
  useEffect(() => {
    const verifyAuth = async () => {
      if (token) {
        try {
          const response = await axios.post(`${API_URL}/auth/verify`, null, {
            params: { token }
          });
          setIsAuthenticated(response.data.valid);
        } catch {
          setIsAuthenticated(false);
          localStorage.removeItem('auth_token');
          setToken(null);
        }
      }
      setLoading(false);
    };
    verifyAuth();
  }, [token]);

  const login = async (pin) => {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, { pin: pin.toString().trim() });
      if (response.data.success) {
        localStorage.setItem('auth_token', response.data.token);
        setToken(response.data.token);
        setIsAuthenticated(true);
        return { success: true };
      }
      return { success: false, message: response.data.message };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, message: error.response?.data?.message || 'Connection error' };
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setIsAuthenticated(false);
  };

  const resetPin = async () => {
    try {
      await axios.post(`${API_URL}/auth/reset`);
      logout();
      return { success: true };
    } catch (error) {
      return { success: false, message: 'Failed to reset PIN' };
    }
  };

  const value = {
    isAuthenticated,
    loading,
    login,
    logout,
    resetPin,
    API_URL
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export default AppContext;
