import axios from "axios";

export const api = axios.create({
    baseURL: import.meta.env.BASE_URL + "api/v1",
    headers: {
        "Content-Type": "application/json",
    },
});

api.interceptors.request.use((config) => {
    const path = window.location.pathname
    // WebApp paths: /webapp (legacy) or /concierge/{slug} or /{slug}
    const isWebApp = path.includes('/webapp') || path.startsWith('/concierge/') || (
        // /{slug} path: any single-segment path that isn't a dashboard route
        !path.includes('/login') && !path.includes('/calendar') &&
        !path.includes('/clients') && !path.includes('/settings') &&
        path.split('/').filter(Boolean).length === 1 && path !== '/'
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
        const isWebApp = path.includes('/webapp') || path.startsWith('/concierge/')
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
