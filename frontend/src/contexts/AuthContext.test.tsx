import { render, screen, act, waitFor } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('@/lib/api', () => {
    const postFn = vi.fn()
    const getFn = vi.fn()
    return {
        api: { get: getFn, post: postFn },
        setAuthExpiredCallback: vi.fn(),
    }
})

const TestComponent = () => {
    const { isAuthenticated, isLoading, user, login, logout } = useAuth()
    return (
        <div>
            <div data-testid="loading">{isLoading ? 'Loading' : 'Ready'}</div>
            <div data-testid="auth-status">{isAuthenticated ? 'Authenticated' : 'Not Authenticated'}</div>
            <div data-testid="username">{user?.username ?? ''}</div>
            <button onClick={login}>Login</button>
            <button onClick={() => { logout() }}>Logout</button>
        </div>
    )
}

describe('AuthContext (cookie-based)', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('shows authenticated when /me succeeds', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any).mockResolvedValueOnce({
            data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null },
        })

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('loading')).toHaveTextContent('Ready')
        })
        expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
        expect(screen.getByTestId('username')).toHaveTextContent('admin')
    })

    it('shows not authenticated when /me returns 401', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any).mockRejectedValueOnce({ response: { status: 401 } })

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('loading')).toHaveTextContent('Ready')
        })
        expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
        expect(screen.getByTestId('username')).toHaveTextContent('')
    })

    it('login triggers checkAuth and updates state', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any)
            .mockRejectedValueOnce({ response: { status: 401 } })
            .mockResolvedValueOnce({
                data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null },
            })

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('loading')).toHaveTextContent('Ready')
        })
        expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')

        await act(async () => {
            screen.getByText('Login').click()
        })

        await waitFor(() => {
            expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
        })
    })

    it('logout calls /auth/logout and clears state', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any).mockResolvedValueOnce({
            data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null },
        })
        ;(api.post as any).mockResolvedValueOnce({ data: { status: 'ok' } })

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('auth-status')).toHaveTextContent('Authenticated')
        })

        await act(async () => {
            screen.getByText('Logout').click()
        })

        expect(api.post).toHaveBeenCalledWith('/auth/logout')
        expect(screen.getByTestId('auth-status')).toHaveTextContent('Not Authenticated')
    })
})
