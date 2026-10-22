package com.containerlens.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class StreamResult(
    @SerialName("stream_status") val streamStatus: String = "SEARCHING",
    @SerialName("confidence_level") val confidenceLevel: String = "LOW",
    @SerialName("container_number") val containerNumber: String = "",
    @SerialName("formatted_number") val formattedNumber: String = "",
    @SerialName("is_valid") val isValid: Boolean = false,
    @SerialName("repaired") val repaired: Boolean = false,
    @SerialName("owner_code") val ownerCode: String = "",
    @SerialName("owner_name") val ownerName: String = "",
    @SerialName("category_desc") val categoryDesc: String = "",
    @SerialName("size_type") val sizeType: String = "",
    @SerialName("size_type_desc") val sizeTypeDesc: String = "",
    @SerialName("check_digit") val checkDigit: String = "",
    @SerialName("expected_check_digit") val expectedCheckDigit: String = "",
    @SerialName("box") val box: List<Int>? = null,
    @SerialName("frame_width") val frameWidth: Int = 1280,
    @SerialName("frame_height") val frameHeight: Int = 720,
    @SerialName("latency_ms") val latencyMs: Float = 0f,
    @SerialName("fps") val fps: Float = 0f
)

enum class ConnectionState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    ERROR
}
