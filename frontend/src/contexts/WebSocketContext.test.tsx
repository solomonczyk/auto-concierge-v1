import { render, screen, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { WebSocketProvider, useWebSocket } from '@/contexts/WebSocketContext'

let mockInstances: MockWebSocket[] = []

class MockWebSocket {
    url: string
    onopen: () => void = () => {}
    onmessage: (event: any) => void = () => {}
    onclose: (event: any) => void = () => {}
    send = vi.fn()
    close = vi.fn()
    readyState: number = WebSocket.CONNECTING

    constructor(url: string) {
        this.url = url
        mockInstances.push(this)
        setTimeout(() => {
            this.readyState = WebSocket.OPEN
            this.onopen()
        }, 10)
    }
}

global.WebSocket = MockWebSocket as any

vi.mock('@/lib/api', () => {
    let callCount = 0
    return {
        api: {
            post: vi.fn(async () => {
                callCount += 1
                return { data: { ticket: `mock-ticket-${callCount}`, expires_in: 45, token_type: 'ws_ticket' } }
            }),
        },
    }
})

const TestComponent = () => {
    const { isConnected, lastMessage } = useWebSocket()
    return (
        <div>
            <div data-testid="status">{isConnected ? 'Connected' : 'Disconnected'}</div>
            <div data-testid="message">{lastMessage ? JSON.stringify(lastMessage) : 'No message'}</div>
        </div>
    )
}

describe('WebSocketProvider (ticket auth)', () => {
    beforeEach(() => {
        mockInstances = []
        vi.useFakeTimers({ shouldAdvanceTime: true })
    })
    afterEach(() => {
        vi.useRealTimers()
    })

    it('fetches ws-ticket then connects with ?ticket=', async () => {
        const { api } = await import('@/lib/api')

        await act(async () => {
            render(
                <WebSocketProvider url="ws://localhost:8000/ws">
                    <TestComponent />
                </WebSocketProvider>
            )
        })

        expect(api.post).toHaveBeenCalledWith('/ws-ticket')
        expect(screen.getByTestId('status')).toHaveTextContent('Disconnected')

        await act(async () => {
            await vi.advanceTimersByTimeAsync(20)
        })

        expect(screen.getByTestId('status')).toHaveTextContent('Connected')
        expect(mockInstances.length).toBe(1)
        expect(mockInstances[0].url).toContain('?ticket=mock-ticket-')
        expect(mockInstances[0].url).not.toContain('token=')
    })

    it('on disconnect fetches a fresh ticket for reconnect', async () => {
        const { api } = await import('@/lib/api')

        await act(async () => {
            render(
                <WebSocketProvider url="ws://localhost:8000/ws">
                    <TestComponent />
                </WebSocketProvider>
            )
        })

        await act(async () => {
            await vi.advanceTimersByTimeAsync(20)
        })
        expect(screen.getByTestId('status')).toHaveTextContent('Connected')

        const firstUrl = mockInstances[0].url
        const callsBefore = (api.post as any).mock.calls.length

        await act(async () => {
            mockInstances[0].onclose({ code: 4401 })
        })
        expect(screen.getByTestId('status')).toHaveTextContent('Disconnected')

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1500)
        })

        expect((api.post as any).mock.calls.length).toBeGreaterThan(callsBefore)
        expect(mockInstances.length).toBe(2)
        expect(mockInstances[1].url).toContain('?ticket=mock-ticket-')
        expect(mockInstances[1].url).not.toBe(firstUrl)
    })
})
