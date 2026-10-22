package com.containerlens.app.data.stream

import android.util.Log
import com.containerlens.app.data.model.ConnectionState
import com.containerlens.app.data.model.StreamResult
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class ContainerStreamClient {

    private val tag = "StreamClient"
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.SECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private var currentUrl: String = "ws://10.0.2.2:8000/api/v1/stream"

    private val _connectionState = MutableStateFlow(ConnectionState.DISCONNECTED)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _streamResult = MutableStateFlow<StreamResult?>(null)
    val streamResult: StateFlow<StreamResult?> = _streamResult.asStateFlow()

    // Backpressure guard: only 1 frame in flight at a time
    private val isFrameInFlight = AtomicBoolean(false)

    fun connect(wsUrl: String) {
        currentUrl = wsUrl
        disconnect()

        _connectionState.value = ConnectionState.CONNECTING
        Log.i(tag, "Connecting to WebSocket: $currentUrl")

        val request = Request.Builder()
            .url(currentUrl)
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(tag, "WebSocket stream connected!")
                _connectionState.value = ConnectionState.CONNECTED
                isFrameInFlight.set(false)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                isFrameInFlight.set(false)
                try {
                    val result = json.decodeFromString<StreamResult>(text)
                    _streamResult.value = result
                } catch (e: Exception) {
                    Log.e(tag, "Failed to parse streaming JSON: ${e.message}")
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(tag, "WebSocket closing: $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(tag, "WebSocket closed: $reason")
                _connectionState.value = ConnectionState.DISCONNECTED
                isFrameInFlight.set(false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(tag, "WebSocket failure: ${t.message}")
                _connectionState.value = ConnectionState.ERROR
                isFrameInFlight.set(false)
            }
        })
    }

    fun disconnect() {
        try {
            webSocket?.close(1000, "User disconnected")
            webSocket = null
        } catch (e: Exception) {
            Log.e(tag, "Error closing WebSocket: ${e.message}")
        }
        _connectionState.value = ConnectionState.DISCONNECTED
        isFrameInFlight.set(false)
    }

    /**
     * Sends compressed JPEG frame bytes over WebSocket if socket is ready and not busy.
     * Returns true if frame was sent, false if dropped due to backpressure.
     */
    fun sendFrame(jpegBytes: ByteArray): Boolean {
        if (_connectionState.value != ConnectionState.CONNECTED) {
            return false
        }

        // Drop frame if previous frame is still in-flight
        if (!isFrameInFlight.compareAndSet(false, true)) {
            return false
        }

        return try {
            val byteString = jpegBytes.toByteString()
            webSocket?.send(byteString) ?: false
        } catch (e: Exception) {
            Log.e(tag, "Error sending frame: ${e.message}")
            isFrameInFlight.set(false)
            false
        }
    }
}
