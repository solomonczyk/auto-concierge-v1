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

const TestComponent = () => {
    const { isConnected, lastMessage } = useWebSocket()
    return (
        <div>
            <div data-testid="status">{isConnected ? 'Connected' : 'Disconnected'}</div>
            <div data-testid="message">{lastMessage ? JSON.stringify(lastMessage) : 'No message'}</div>
        </div>
    )
}

describe('WebSocketProvider (cookie auth)', () => {
    beforeEach(() => {
        mockInstances = []
        vi.useFakeTimers({ shouldAdvanceTime: true })
    })
    afterEach(() => {
        vi.useRealTimers()
    })

    it('connects with cookie auth (no ticket/token in URL)', async () => {
        await act(async () => {
            render(
                <WebSocketProvider url="ws://localhost:8000/ws">
                    <TestComponent />
                </WebSocketProvider>
            )
        })

        expect(screen.getByTestId('status')).toHaveTextContent('Disconnected')

        await act(async () => {
            await vi.advanceTimersByTimeAsync(20)
        })

        expect(screen.getByTestId('status')).toHaveTextContent('Connected')
        expect(mockInstances.length).toBe(1)
        expect(mockInstances[0].url).not.toContain('?ticket=')
        expect(mockInstances[0].url).not.toContain('token=')
        expect(mockInstances[0].url).toBe('ws://localhost:8000/ws')
    })

    it('on disconnect schedules reconnect with same URL (cookie auth)', async () => {
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

        await act(async () => {
            mockInstances[0].onclose({ code: 4401 })
        })
        expect(screen.getByTestId('status')).toHaveTextContent('Disconnected')

        await act(async () => {
            await vi.advanceTimersByTimeAsync(1500)
        })

        expect(mockInstances.length).toBe(2)
        expect(mockInstances[1].url).toBe(firstUrl)
        expect(mockInstances[1].url).not.toContain('?ticket=')
        expect(mockInstances[1].url).not.toContain('token=')
    })
})
