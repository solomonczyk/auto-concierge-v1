import axios from "axios";

export const api = axios.create({
    baseURL: import.meta.env.BASE_URL + "api/v1",
    headers: {
        "Content-Type": "application/json",
    },
});

api.interceptors.request.use((config) => {
    const path = window.location.pathname
    const segments = path.split('/').filter(Boolean)
    // WebApp = public booking only. Dashboard (/concierge, /concierge/calendar etc.) needs auth.
    const isWebApp = path.includes('/webapp') || (
        segments[0] === 'concierge' && segments[1] && !['login', 'calendar', 'clients', 'settings'].includes(segments[1])
    ) || (
        segments.length === 1 && segments[0] !== 'concierge'  // /{slug} legacy
    )
    if (isWebApp) {
        if (config.headers) delete config.headers["Authorization"]
        return config
    }

    const token = localStorage.getItem("token");
    if (token && config.headers) {
        config.headers["Authorization"] = "Bearer " + token;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const path = window.location.pathname
        const segments = path.split('/').filter(Boolean)
        const isWebApp = path.includes('/webapp') || (
            segments[0] === 'concierge' && segments[1] && !['login', 'calendar', 'clients', 'settings'].includes(segments[1])
        ) || (segments.length === 1 && segments[0] !== 'concierge')
        if (error.response?.status === 401) {
            if (isWebApp) return Promise.reject(error)
            // If session expired, redirect to login
            if (!window.location.pathname.includes('/login')) {
                localStorage.removeItem('token');
                window.location.href = import.meta.env.BASE_URL + "login";
            }
        }
        return Promise.reject(error);
    }
);
