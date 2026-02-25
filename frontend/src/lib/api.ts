import axios from "axios";

export const api = axios.create({
    baseURL: import.meta.env.BASE_URL + "api/v1",
    headers: {
        "Content-Type": "application/json",
    },
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem("token");
    if (token && config.headers) {
        config.headers["Authorization"] = "Bearer " + token;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // If session expired, redirect to login
            if (!window.location.pathname.includes('/login')) {
                localStorage.removeItem('token');
                window.location.href = import.meta.env.BASE_URL + "login";
            }
        }
        return Promise.reject(error);
    }
);
