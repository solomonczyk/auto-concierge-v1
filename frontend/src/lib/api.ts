import axios from "axios"

export const api = axios.create({
    baseURL: import.meta.env.BASE_URL + "api/v1",
    headers: {
        "Content-Type": "application/json",
    },
    withCredentials: true,
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
