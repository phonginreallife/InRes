'use client';

import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Hook for token-level streaming chat with the AI agent.
 * 
 * This hook connects to the /ws/stream endpoint which provides
 * true token-by-token streaming from the LLM.
 * 
 * Features:
 * - Token streaming (smoother than block streaming)
 * - Tool support
 * - Interrupt/stop streaming
 * - Conversation history management
 * 
 * @param {string} authToken - JWT token for authentication
 * @param {Object} options - Configuration options
 * @returns {Object} Chat state and functions
 */
export function useStreamingChat(authToken = null, options = {}) {
  const { autoConnect = false } = options;

  // State
  const [messages, setMessages] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [isSending, setIsSending] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);

  // Refs
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);

  // Get WebSocket URL
  const getWsUrl = useCallback(() => {
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
    // Use AI Agent port (default 8002)
    const host = window.location.hostname;
    const port = process.env.NEXT_PUBLIC_AGENT_PORT || '8002';
    return `${scheme}://${host}:${port}/ws/stream?token=${authToken}`;
  }, [authToken]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!authToken) {
      console.warn('[StreamingChat] No auth token, cannot connect');
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      console.log('[StreamingChat] Already connected');
      return;
    }

    const wsUrl = getWsUrl();
    console.log('[StreamingChat] Connecting to:', wsUrl);
    setConnectionStatus('connecting');

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[StreamingChat] Connected');
        setConnectionStatus('connected');
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('[StreamingChat] Message:', data.type);

          switch (data.type) {
            case 'session_created':
              setSessionId(data.session_id);
              console.log('[StreamingChat] Session:', data.session_id);
              break;

            case 'delta':
              // Token-level streaming - append each token
              if (data.content) {
                setMessages(prev => {
                  const lastMsg = prev[prev.length - 1];
                  if (lastMsg?.role === 'assistant' && lastMsg?.isStreaming) {
                    return [...prev.slice(0, -1), {
                      ...lastMsg,
                      content: (lastMsg.content || '') + data.content,
                    }];
                  }
                  // First token - create new message
                  return [...prev, {
                    role: 'assistant',
                    content: data.content,
                    timestamp: new Date().toISOString(),
                    isStreaming: true,
                  }];
                });
              }
              break;

            case 'tool_use':
              // Tool is being called
              setMessages(prev => [...prev, {
                role: 'assistant',
                type: 'tool_use',
                toolName: data.name,
                toolInput: data.input,
                toolId: data.id,
                timestamp: new Date().toISOString(),
              }]);
              break;

            case 'tool_result':
              // Tool execution result
              setMessages(prev => [...prev, {
                role: 'tool',
                type: 'tool_result',
                toolId: data.tool_use_id,
                content: data.content,
                isError: data.is_error,
                timestamp: new Date().toISOString(),
              }]);
              break;

            case 'complete':
              // Response complete
              setIsSending(false);
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant' && lastMsg?.isStreaming) {
                  newMessages[newMessages.length - 1] = {
                    ...lastMsg,
                    isStreaming: false,
                  };
                }
                return newMessages;
              });
              break;

            case 'interrupted':
              setIsSending(false);
              setMessages(prev => {
                const newMessages = [...prev];
                const lastMsg = newMessages[newMessages.length - 1];
                if (lastMsg?.role === 'assistant' && lastMsg?.isStreaming) {
                  newMessages[newMessages.length - 1] = {
                    ...lastMsg,
                    isStreaming: false,
                    interrupted: true,
                  };
                }
                return newMessages;
              });
              break;

            case 'error':
              setError(data.error);
              setIsSending(false);
              break;

            case 'history_cleared':
              setMessages([]);
              break;

            default:
              console.log('[StreamingChat] Unknown message type:', data.type);
          }
        } catch (e) {
          console.error('[StreamingChat] Parse error:', e);
        }
      };

      ws.onclose = (event) => {
        console.log('[StreamingChat] Disconnected:', event.code, event.reason);
        setConnectionStatus('disconnected');
        wsRef.current = null;

        // Auto-reconnect on abnormal close
        if (event.code !== 1000 && event.code !== 4001) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[StreamingChat] Attempting reconnect...');
            connect();
          }, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('[StreamingChat] WebSocket error:', error);
        setError('Connection error');
      };

    } catch (e) {
      console.error('[StreamingChat] Connection failed:', e);
      setError('Failed to connect');
      setConnectionStatus('disconnected');
    }
  }, [authToken, getWsUrl]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000, 'User disconnect');
      wsRef.current = null;
    }
    setConnectionStatus('disconnected');
  }, []);

  // Send message
  const sendMessage = useCallback((prompt) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('[StreamingChat] Not connected');
      return false;
    }

    if (!prompt?.trim()) {
      return false;
    }

    // Add user message to state
    setMessages(prev => [...prev, {
      role: 'user',
      content: prompt,
      timestamp: new Date().toISOString(),
    }]);

    // Send to WebSocket
    wsRef.current.send(JSON.stringify({
      type: 'chat',
      prompt: prompt,
      session_id: sessionId,
    }));

    setIsSending(true);
    return true;
  }, [sessionId]);

  // Stop streaming
  const stopStreaming = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'interrupt' }));
    }
  }, []);

  // Clear history
  const clearHistory = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'clear_history' }));
    }
    setMessages([]);
  }, []);

  // Auto-connect effect
  useEffect(() => {
    if (autoConnect && authToken) {
      connect();
    }
    return () => disconnect();
  }, [autoConnect, authToken, connect, disconnect]);

  return {
    // State
    messages,
    setMessages,
    connectionStatus,
    isSending,
    sessionId,
    error,
    
    // Actions
    connect,
    disconnect,
    sendMessage,
    stopStreaming,
    clearHistory,
    
    // Computed
    isConnected: connectionStatus === 'connected',
    isConnecting: connectionStatus === 'connecting',
  };
}

export default useStreamingChat;
