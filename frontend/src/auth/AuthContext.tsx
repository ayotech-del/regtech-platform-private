import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { clearStoredApiKey, getStoredApiKey, setStoredApiKey } from "../api/client";

interface AuthContextValue {
  apiKey: string | null;
  connect: (key: string) => void;
  disconnect: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKey] = useState<string | null>(() => getStoredApiKey());

  const connect = useCallback((key: string) => {
    setStoredApiKey(key);
    setApiKey(key);
  }, []);

  const disconnect = useCallback(() => {
    clearStoredApiKey();
    setApiKey(null);
  }, []);

  return <AuthContext.Provider value={{ apiKey, connect, disconnect }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
