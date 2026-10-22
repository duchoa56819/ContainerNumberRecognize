package com.containerlens.app.ui.camera

import android.content.Context
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.util.Log
import android.util.Size
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.containerlens.app.data.stream.ContainerStreamClient
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.util.concurrent.Executors

@Composable
fun StreamingCameraView(
    streamClient: ContainerStreamClient,
    torchEnabled: Boolean,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val cameraExecutor = remember { Executors.newSingleThreadExecutor() }
    var camera: Camera? = remember { null }

    DisposableEffect(Unit) {
        onDispose {
            cameraExecutor.shutdown()
        }
    }

    AndroidView(
        factory = { ctx ->
            val previewView = PreviewView(ctx).apply {
                scaleType = PreviewView.ScaleType.FILL_CENTER
            }

            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
            cameraProviderFuture.addListener({
                val cameraProvider = cameraProviderFuture.get()

                val preview = Preview.Builder()
                    .build()
                    .also {
                        it.setSurfaceProvider(previewView.surfaceProvider)
                    }

                // Streaming Image Analysis: keep only the latest frame
                val imageAnalysis = ImageAnalysis.Builder()
                    .setTargetResolution(Size(1280, 720))
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                    .build()

                var lastFrameTime = 0L
                val minIntervalMs = 120L // ~8 FPS max stream rate

                imageAnalysis.setAnalyzer(cameraExecutor) { imageProxy ->
                    val now = System.currentTimeMillis()
                    if (now - lastFrameTime < minIntervalMs) {
                        imageProxy.close()
                        return@setAnalyzer
                    }

                    try {
                        val jpegBytes = imageProxyToJpegByteArray(imageProxy)
                        if (jpegBytes != null && jpegBytes.isNotEmpty()) {
                            val sent = streamClient.sendFrame(jpegBytes)
                            if (sent) {
                                lastFrameTime = now
                            }
                        }
                    } catch (e: Exception) {
                        Log.e("CameraStream", "Error converting frame to JPEG: ${e.message}")
                    } finally {
                        imageProxy.close()
                    }
                }

                val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA

                try {
                    cameraProvider.unbindAll()
                    camera = cameraProvider.bindToLifecycle(
                        lifecycleOwner,
                        cameraSelector,
                        preview,
                        imageAnalysis
                    )
                    camera?.cameraControl?.enableTorch(torchEnabled)
                } catch (e: Exception) {
                    Log.e("CameraStream", "Use case binding failed", e)
                }
            }, ContextCompat.getMainExecutor(ctx))

            previewView
        },
        update = {
            camera?.cameraControl?.enableTorch(torchEnabled)
        },
        modifier = modifier.fillMaxSize()
    )
}

/**
 * Fast conversion from CameraX YUV_420_888 ImageProxy to compressed JPEG bytes.
 */
private fun imageProxyToJpegByteArray(image: ImageProxy): ByteArray? {
    if (image.format != ImageFormat.YUV_420_888) return null

    val yBuffer = image.planes[0].buffer
    val uBuffer = image.planes[1].buffer
    val vBuffer = image.planes[2].buffer

    val ySize = yBuffer.remaining()
    val uSize = uBuffer.remaining()
    val vSize = vBuffer.remaining()

    val nv21 = ByteArray(ySize + uSize + vSize)

    yBuffer.get(nv21, 0, ySize)
    vBuffer.get(nv21, ySize, vSize)
    uBuffer.get(nv21, ySize + vSize, uSize)

    val yuvImage = YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
    val out = ByteArrayOutputStream()
    // Quality 75 provides great OCR accuracy while keeping payload under ~40 KB
    yuvImage.compressToJpeg(Rect(0, 0, image.width, image.height), 75, out)
    return out.toByteArray()
}
