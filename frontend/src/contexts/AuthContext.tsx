import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react"
import { api, setAuthExpiredCallback } from "@/lib/api"

interface UserInfo {
    user_id: number
    username: string
    role: string | null
    tenant_id: number | null
    tenant_slug: string | null
}

interface AuthContextType {
    isAuthenticated: boolean
    isLoading: boolean
    user: UserInfo | null
    login: () => void
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [isAuthenticated, setIsAuthenticated] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const [user, setUser] = useState<UserInfo | null>(null)

    const checkAuth = useCallback(async () => {
        try {
            const response = await api.get("/me")
            setUser(response.data)
            setIsAuthenticated(true)
        } catch {
            setUser(null)
            setIsAuthenticated(false)
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        checkAuth()
    }, [checkAuth])

    useEffect(() => {
        setAuthExpiredCallback(() => {
            setUser(null)
            setIsAuthenticated(false)
        })
        return () => setAuthExpiredCallback(() => {})
    }, [])

    const login = () => {
        checkAuth()
    }

    const logout = async () => {
        try {
            await api.post("/auth/logout")
        } catch {
            // ignore logout errors
        }
        setUser(null)
        setIsAuthenticated(false)
    }

    return (
        <AuthContext.Provider value={{ isAuthenticated, isLoading, user, login, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error("useAuth must be used within an AuthProvider")
    }
    return context
}
