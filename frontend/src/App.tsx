import { Routes, Route, Navigate, Outlet } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import DashboardLayout from '@/components/dashboard/DashboardLayout'
import KanbanPage from '@/pages/KanbanPage'
import CalendarPage from '@/pages/CalendarPage'
import LoginPage from '@/pages/LoginPage'
import BookingPage from '@/pages/WebApp/BookingPage'
import ClientsPage from '@/pages/ClientsPage'
import SettingsPage from '@/pages/SettingsPage'

function RequireAuth() {
    const { isAuthenticated } = useAuth();
    return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
}

import { WebSocketProvider } from '@/contexts/WebSocketContext'

function App() {
    const baseUrl = import.meta.env.BASE_URL

    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = wsProtocol + '//' + window.location.host + baseUrl + 'api/v1/ws'
    return (
        <AuthProvider>
            <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/webapp" element={<BookingPage />} />

                <Route element={<RequireAuth />}>
                    <Route path="/" element={
                        <WebSocketProvider url={wsUrl}>
                            <DashboardLayout />
                        </WebSocketProvider>
                    }>
                        <Route index element={<KanbanPage />} />
                        <Route path="calendar" element={<CalendarPage />} />
                        <Route path="clients" element={<ClientsPage />} />
                        <Route path="settings" element={<SettingsPage />} />
                    </Route>
                </Route>
            </Routes>
        </AuthProvider>
    )
}

export default App
