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
  const [settings, setSettings] = useState(null);
  const [paperMode, setPaperMode] = useState(true);
  const [solPrice, setSolPrice] = useState(150);
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

  // Fetch settings
  useEffect(() => {
    const fetchSettings = async () => {
      if (isAuthenticated) {
        try {
          const response = await axios.get(`${API_URL}/settings`);
          setSettings(response.data);
          setPaperMode(response.data.paper_mode);
        } catch (error) {
          console.error('Error fetching settings:', error);
        }
      }
    };
    fetchSettings();
  }, [isAuthenticated]);

  // Fetch SOL price
  useEffect(() => {
    const fetchSolPrice = async () => {
      try {
        const response = await axios.get(`${API_URL}/market/sol-price`);
        setSolPrice(response.data.price);
      } catch {
        // Use default price
      }
    };
    fetchSolPrice();
    const interval = setInterval(fetchSolPrice, 60000);
    return () => clearInterval(interval);
  }, []);

  const login = async (pin) => {
    try {
      const response = await axios.post(`${API_URL}/auth/login`, { pin });
      if (response.data.success) {
        localStorage.setItem('auth_token', response.data.token);
        setToken(response.data.token);
        setIsAuthenticated(true);
        return { success: true };
      }
      return { success: false, message: response.data.message };
    } catch (error) {
      return { success: false, message: 'Connection error' };
    }
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setIsAuthenticated(false);
    setSettings(null);
  };

  const updateSettings = async (newSettings) => {
    try {
      const response = await axios.put(`${API_URL}/settings`, newSettings);
      setSettings(response.data);
      setPaperMode(response.data.paper_mode);
      return { success: true };
    } catch (error) {
      return { success: false, message: 'Failed to update settings' };
    }
  };

  const togglePaperMode = useCallback(async () => {
    if (settings) {
      const newMode = !paperMode;
      await updateSettings({ ...settings, paper_mode: newMode });
    }
  }, [settings, paperMode]);

  const value = {
    isAuthenticated,
    loading,
    settings,
    paperMode,
    solPrice,
    login,
    logout,
    updateSettings,
    togglePaperMode,
    API_URL
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

export default AppContext;
