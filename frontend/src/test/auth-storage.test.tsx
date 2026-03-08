/**
 * Auth storage tests — cookie-only flow, no localStorage for token.
 * High-risk audit: ensure no token in localStorage, auth via cookie + /me.
 */
import { render, screen, act, waitFor, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/contexts/AuthContext'
import LoginPage from '@/pages/LoginPage'

vi.mock('@/lib/api', () => {
    const postFn = vi.fn()
    const getFn = vi.fn()
    return {
        api: { get: getFn, post: postFn },
        setAuthExpiredCallback: vi.fn(),
    }
})

describe('Auth storage (cookie-only)', () => {
    let setItemSpy: ReturnType<typeof vi.spyOn>
    let getItemSpy: ReturnType<typeof vi.spyOn>

    beforeEach(() => {
        vi.clearAllMocks()
        setItemSpy = vi.spyOn(Storage.prototype, 'setItem')
        getItemSpy = vi.spyOn(Storage.prototype, 'getItem')
    })

    afterEach(() => {
        setItemSpy.mockRestore()
        getItemSpy.mockRestore()
    })

    it('login flow does not write token to localStorage', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any)
            .mockRejectedValueOnce({ response: { status: 401 } })
            .mockResolvedValue({ data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null } })
        ;(api.post as any).mockResolvedValueOnce({ data: { status: 'ok' } })

        render(
            <BrowserRouter>
                <AuthProvider>
                    <LoginPage />
                </AuthProvider>
            </BrowserRouter>
        )

        await waitFor(() => {
            expect(screen.getByPlaceholderText(/например: admin/i)).toBeInTheDocument()
        })

        const userInput = screen.getByPlaceholderText(/например: admin/i)
        const passInput = screen.getByPlaceholderText(/ваш пароль/i)
        fireEvent.change(userInput, { target: { value: 'admin' } })
        fireEvent.change(passInput, { target: { value: 'admin' } })

        await act(async () => {
            screen.getByRole('button', { name: /войти/i }).click()
        })

        await waitFor(() => {
            expect(api.post).toHaveBeenCalledWith(
                '/login/access-token',
                expect.any(URLSearchParams),
                expect.objectContaining({ headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
            )
        })

        const tokenSetCalls = setItemSpy.mock.calls.filter(
            (c) => c[0] === 'token' || c[0] === 'access_token'
        )
        expect(tokenSetCalls).toHaveLength(0)
    })

    it('bootstrap session uses /me endpoint', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any).mockResolvedValueOnce({
            data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null },
        })

        const TestComponent = () => {
            const { isAuthenticated, isLoading } = useAuth()
            return (
                <div>
                    <span data-testid="loading">{isLoading ? 'Loading' : 'Ready'}</span>
                    <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
                </div>
            )
        }

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('loading')).toHaveTextContent('Ready')
        })
        expect(api.get).toHaveBeenCalledWith('/me')
        expect(screen.getByTestId('auth')).toHaveTextContent('yes')
    })

    it('logout clears auth state without localStorage', async () => {
        const { api } = await import('@/lib/api')
        ;(api.get as any).mockResolvedValueOnce({
            data: { user_id: 1, username: 'admin', role: 'admin', tenant_id: 1, tenant_slug: null },
        })
        ;(api.post as any).mockResolvedValueOnce({ data: { status: 'ok' } })

        const TestComponent = () => {
            const { isAuthenticated, logout } = useAuth()
            return (
                <div>
                    <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
                    <button onClick={() => logout()}>Logout</button>
                </div>
            )
        }

        render(
            <AuthProvider>
                <TestComponent />
            </AuthProvider>
        )

        await waitFor(() => {
            expect(screen.getByTestId('auth')).toHaveTextContent('yes')
        })

        await act(async () => {
            screen.getByText('Logout').click()
        })

        expect(api.post).toHaveBeenCalledWith('/auth/logout')
        expect(screen.getByTestId('auth')).toHaveTextContent('no')

        const tokenCalls = [
            ...setItemSpy.mock.calls.filter((c) => c[0] === 'token' || c[0] === 'access_token'),
            ...getItemSpy.mock.calls.filter((c) => c[0] === 'token' || c[0] === 'access_token'),
        ]
        expect(tokenCalls).toHaveLength(0)
    })

    it('no legacy token storage in auth-related source files', () => {
        const { readFileSync } = require('fs')
        const { join, dirname } = require('path')
        const { fileURLToPath } = require('url')
        const __dirname = dirname(fileURLToPath(import.meta.url))
        const srcRoot = join(__dirname, '..')
        const authFiles = [
            join(srcRoot, 'lib', 'api.ts'),
            join(srcRoot, 'contexts', 'AuthContext.tsx'),
            join(srcRoot, 'pages', 'LoginPage.tsx'),
        ]
        const badPatterns = [
            /localStorage\.setItem\s*\(\s*['"]token['"]/,
            /localStorage\.setItem\s*\(\s*['"]access_token['"]/,
            /localStorage\.getItem\s*\(\s*['"]token['"]/,
            /localStorage\.getItem\s*\(\s*['"]access_token['"]/,
        ]
        for (const file of authFiles) {
            const content = readFileSync(file, 'utf-8')
            for (const pattern of badPatterns) {
                expect(content).not.toMatch(pattern)
            }
        }
    })
})
