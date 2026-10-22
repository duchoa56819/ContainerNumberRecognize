package com.containerlens.app.ui.overlay

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import com.containerlens.app.data.model.StreamResult

@Composable
fun LiveBoundingBoxOverlay(
    streamResult: StreamResult?,
    modifier: Modifier = Modifier
) {
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val alphaAnim by infiniteTransition.animateFloat(
        initialValue = 0.4f,
        targetValue = 0.95f,
        animationSpec = infiniteRepeatable(
            animation = tween(1200, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "alpha"
    )

    Canvas(modifier = modifier.fillMaxSize()) {
        val screenW = size.width
        val screenH = size.height

        // 1. Draw Static Alignment Reticle in Center
        val reticleW = screenW * 0.82f
        val reticleH = screenH * 0.32f
        val reticleLeft = (screenW - reticleW) / 2f
        val reticleTop = (screenH - reticleH) / 2.3f

        // Center reticle
        drawRoundRect(
            color = Color(0x3338BDF8),
            topLeft = Offset(reticleLeft, reticleTop),
            size = Size(reticleW, reticleH),
            cornerRadius = CornerRadius(16f, 16f),
            style = Stroke(
                width = 3f,
                pathEffect = PathEffect.dashPathEffect(floatArrayOf(20f, 15f), 0f)
            )
        )

        // Corner brackets on reticle
        val cornerLen = 30f
        val bracketColor = Color(0xFF38BDF8)
        val bracketStroke = 6f

        // Top-left
        drawLine(bracketColor, Offset(reticleLeft, reticleTop), Offset(reticleLeft + cornerLen, reticleTop), bracketStroke)
        drawLine(bracketColor, Offset(reticleLeft, reticleTop), Offset(reticleLeft, reticleTop + cornerLen), bracketStroke)

        // Top-right
        drawLine(bracketColor, Offset(reticleLeft + reticleW, reticleTop), Offset(reticleLeft + reticleW - cornerLen, reticleTop), bracketStroke)
        drawLine(bracketColor, Offset(reticleLeft + reticleW, reticleTop), Offset(reticleLeft + reticleW, reticleTop + cornerLen), bracketStroke)

        // Bottom-left
        drawLine(bracketColor, Offset(reticleLeft, reticleTop + reticleH), Offset(reticleLeft + cornerLen, reticleTop + reticleH), bracketStroke)
        drawLine(bracketColor, Offset(reticleLeft, reticleTop + reticleH), Offset(reticleLeft, reticleTop + reticleH - cornerLen), bracketStroke)

        // Bottom-right
        drawLine(bracketColor, Offset(reticleLeft + reticleW, reticleTop + reticleH), Offset(reticleLeft + reticleW - cornerLen, reticleTop + reticleH), bracketStroke)
        drawLine(bracketColor, Offset(reticleLeft + reticleW, reticleTop + reticleH), Offset(reticleLeft + reticleW, reticleTop + reticleH - cornerLen), bracketStroke)

        // 2. Draw Dynamic Real-time Detected Region Bounding Box
        val box = streamResult?.box
        val frameW = streamResult?.frameWidth ?: 1280
        val frameH = streamResult?.frameHeight ?: 720

        if (box != null && box.size == 4 && frameW > 0 && frameH > 0) {
            val scaleX = screenW / frameW.toFloat()
            val scaleY = screenH / frameH.toFloat()

            val bx1 = box[0] * scaleX
            val by1 = box[1] * scaleY
            val bx2 = box[2] * scaleX
            val by2 = box[3] * scaleY

            val boxColor = when {
                streamResult.isValid && !streamResult.repaired -> Color(0xFF22C55E) // Green
                streamResult.isValid && streamResult.repaired -> Color(0xFFF59E0B) // Amber
                else -> Color(0xFF06B6D4) // Cyan
            }

            // Outer glow
            drawRoundRect(
                color = boxColor.copy(alpha = alphaAnim),
                topLeft = Offset(bx1, by1),
                size = Size(bx2 - bx1, by2 - by1),
                cornerRadius = CornerRadius(12f, 12f),
                style = Stroke(width = 6f)
            )

            // Fill tint
            drawRoundRect(
                color = boxColor.copy(alpha = 0.12f),
                topLeft = Offset(bx1, by1),
                size = Size(bx2 - bx1, by2 - by1),
                cornerRadius = CornerRadius(12f, 12f)
            )
        }
    }
}
