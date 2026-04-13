import axios from "axios"

const CSRF_COOKIE_NAME = "csrf_token"

function getCsrfToken(): string | null {
    if (typeof document === "undefined") return null
    const match = document.cookie.match(new RegExp(`(?:^|; )${CSRF_COOKIE_NAME}=([^;]*)`))
    return match ? decodeURIComponent(match[1]) : null
}

const apiBase = (import.meta.env.BASE_URL || "/concierge/").replace(/\/$/, "") + "/api/v1"
export const api = axios.create({
    baseURL: apiBase,
    headers: {
        "Content-Type": "application/json",
    },
    withCredentials: true,
})

api.interceptors.request.use((config) => {
    const method = (config.method ?? "get").toUpperCase()
    if (["POST", "PATCH", "PUT", "DELETE"].includes(method)) {
        const token = getCsrfToken()
        if (token) config.headers["X-CSRF-Token"] = token
    }
    return config
})

let onAuthExpired: (() => void) | null = null

export function setAuthExpiredCallback(callback: () => void) {
    onAuthExpired = callback
}

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            const path = window.location.pathname
            const segments = path.split('/').filter(Boolean)
            const isWebApp = path.includes('/webapp') || (
                segments[0] === 'concierge' && segments[1] && !['login', 'calendar', 'clients', 'settings'].includes(segments[1])
            ) || (segments.length === 1 && segments[0] !== 'concierge')
            const isAuthCheck = error.config?.url?.includes('/me')

            if (!isWebApp && !isAuthCheck) {
                onAuthExpired?.()
            }
        }
        return Promise.reject(error)
    }
)
