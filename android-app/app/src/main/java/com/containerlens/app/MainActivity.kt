package com.containerlens.app

import android.Manifest
import android.content.Context
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import com.containerlens.app.data.stream.ContainerStreamClient
import com.containerlens.app.ui.camera.StreamingCameraView
import com.containerlens.app.ui.hud.LiveStreamHUD
import com.containerlens.app.ui.overlay.LiveBoundingBoxOverlay

class MainActivity : ComponentActivity() {

    private val streamClient = ContainerStreamClient()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    primary = Color(0xFF0284C7),
                    background = Color(0xFF0B0F19),
                    surface = Color(0xFF1E293B)
                )
            ) {
                MainStreamingScreen(streamClient = streamClient)
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        streamClient.disconnect()
    }
}

@Composable
fun MainStreamingScreen(streamClient: ContainerStreamClient) {
    val context = LocalContext.current
    var hasCameraPermission by remember { mutableStateOf(false) }
    var torchEnabled by remember { mutableStateOf(false) }
    var serverUrl by remember { mutableStateOf("ws://10.0.2.2:8000/api/v1/stream") }

    val connectionState by streamClient.connectionState.collectAsState()
    val streamResult by streamClient.streamResult.collectAsState()

    // Request Camera Permission on launch
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasCameraPermission = granted
    }

    LaunchedEffect(Unit) {
        permissionLauncher.launch(Manifest.permission.CAMERA)
        streamClient.connect(serverUrl)
    }

    // Haptic feedback on newly locked valid container
    var lastLockedCode by remember { mutableStateOf("") }
    LaunchedEffect(streamResult) {
        val res = streamResult
        if (res != null && res.isValid && res.containerNumber != lastLockedCode) {
            lastLockedCode = res.containerNumber
            triggerHapticFeedback(context)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black)
    ) {
        if (hasCameraPermission) {
            // 1. CameraX Streaming Feed
            StreamingCameraView(
                streamClient = streamClient,
                torchEnabled = torchEnabled,
                modifier = Modifier.fillMaxSize()
            )

            // 2. Real-Time Dynamic Bounding Box Overlay
            LiveBoundingBoxOverlay(
                streamResult = streamResult,
                modifier = Modifier.fillMaxSize()
            )

            // 3. Status HUD and Result Bottom Card
            LiveStreamHUD(
                connectionState = connectionState,
                streamResult = streamResult,
                torchEnabled = torchEnabled,
                onToggleTorch = { torchEnabled = !torchEnabled },
                currentServerUrl = serverUrl,
                onUpdateServerUrl = { newUrl ->
                    serverUrl = newUrl
                    streamClient.connect(newUrl)
                },
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

private fun triggerHapticFeedback(context: Context) {
    try {
        val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(
                VibrationEffect.createOneShot(100, VibrationEffect.DEFAULT_AMPLITUDE)
            )
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(100)
        }
    } catch (e: Exception) {
        // Ignore haptic errors on emulators
    }
}
