import React, { createContext, useContext, useEffect, useState, ReactNode, useRef } from 'react'
import { api } from '@/lib/api'

interface WebSocketContextType {
    isConnected: boolean
    lastMessage: any | null
    sendMessage: (message: any) => void
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined)

interface WebSocketProviderProps {
    url: string
    children: ReactNode
}

async function fetchWsTicket(): Promise<string> {
    const response = await api.post('/ws-ticket')
    return response.data.ticket
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ url, children }) => {
    const [isConnected, setIsConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState<any | null>(null)
    const ws = useRef<WebSocket | null>(null)
    const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
    const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null)
    const reconnectAttempts = useRef(0)
    const MAX_RECONNECT_ATTEMPTS = 15
    const isUnmounted = useRef(false)

    useEffect(() => {
        isUnmounted.current = false

        const clearHeartbeat = () => {
            if (!heartbeatTimer.current) return
            clearInterval(heartbeatTimer.current)
            heartbeatTimer.current = null
        }

        const scheduleReconnect = () => {
            if (isUnmounted.current) return
            if (reconnectAttempts.current >= MAX_RECONNECT_ATTEMPTS) {
                console.warn('WS max reconnect attempts reached, giving up')
                return
            }
            const delay = Math.min(1000 * (2 ** reconnectAttempts.current), 10000)
            reconnectAttempts.current += 1
            reconnectTimer.current = setTimeout(() => { connect() }, delay)
        }

        const connect = async () => {
            let ticket: string
            try {
                ticket = await fetchWsTicket()
            } catch (err) {
                console.warn('WS ticket fetch failed, scheduling reconnect', err)
                scheduleReconnect()
                return
            }

            const separator = url.includes('?') ? '&' : '?'
            const wsUrl = url + separator + `ticket=${encodeURIComponent(ticket)}`
            const socket = new WebSocket(wsUrl)
            ws.current = socket

            socket.onopen = () => {
                setIsConnected(true)
                reconnectAttempts.current = 0
                console.log('WebSocket connected (ticket auth)')

                clearHeartbeat()
                heartbeatTimer.current = setInterval(() => {
                    if (ws.current?.readyState === WebSocket.OPEN)
                        ws.current.send(JSON.stringify({ type: 'ping' }))
                }, 25000)
            }

            socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)
                    setLastMessage(data)
                } catch (e) {
                    console.error('Failed to parse WebSocket message', e)
                }
            }

            socket.onclose = (event) => {
                setIsConnected(false)
                clearHeartbeat()
                console.log(`WebSocket disconnected (code: ${event.code})`)
                scheduleReconnect()
            }
        }

        connect()
        return () => {
            isUnmounted.current = true
            clearHeartbeat()
            if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
            ws.current?.close()
        }
    }, [url])

    const sendMessage = (message: any) => {
        if (ws.current && ws.current.readyState === WebSocket.OPEN) {
            ws.current.send(JSON.stringify(message))
        }
    }

    return (
        <WebSocketContext.Provider value={{ isConnected, lastMessage, sendMessage }}>
            {children}
        </WebSocketContext.Provider>
    )
}

export const useWebSocket = () => {
    const context = useContext(WebSocketContext)
    if (context === undefined) {
        throw new Error('useWebSocket must be used within a WebSocketProvider')
    }
    return context
}
