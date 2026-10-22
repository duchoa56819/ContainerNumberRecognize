package com.containerlens.app.ui.hud

import android.widget.Toast
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.FlashOff
import androidx.compose.material.icons.filled.FlashOn
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.containerlens.app.data.model.ConnectionState
import com.containerlens.app.data.model.StreamResult

@Composable
fun LiveStreamHUD(
    connectionState: ConnectionState,
    streamResult: StreamResult?,
    torchEnabled: Boolean,
    onToggleTorch: () -> Unit,
    currentServerUrl: String,
    onUpdateServerUrl: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    var showSettingsDialog by remember { mutableStateOf(false) }

    Box(modifier = modifier.fillMaxSize()) {
        // 1. Top Bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = 40.dp, start = 16.dp, end = 16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Status Pill
            val (statusText, statusBg, dotColor) = when (connectionState) {
                ConnectionState.CONNECTED -> {
                    val lat = streamResult?.latencyMs?.toInt() ?: 0
                    val fps = streamResult?.fps ?: 0f
                    Triple("LIVE STREAM: ${lat}ms | ${fps} FPS", Color(0xCC0F172A), Color(0xFF22C55E))
                }
                ConnectionState.CONNECTING -> Triple("CONNECTING...", Color(0xCC0F172A), Color(0xFFF59E0B))
                ConnectionState.DISCONNECTED -> Triple("DISCONNECTED", Color(0xCC0F172A), Color(0xFF94A3B8))
                ConnectionState.ERROR -> Triple("OFFLINE - CHECK IP", Color(0xCC0F172A), Color(0xFFEF4444))
            }

            Surface(
                shape = RoundedCornerShape(20.dp),
                color = statusBg,
                shadowElevation = 4.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(dotColor)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = statusText,
                        color = Color.White,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Bold,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            // Action Buttons
            Row {
                IconButton(
                    onClick = onToggleTorch,
                    modifier = Modifier
                        .size(42.dp)
                        .background(Color(0xCC0F172A), CircleShape)
                ) {
                    Icon(
                        imageVector = if (torchEnabled) Icons.Default.FlashOn else Icons.Default.FlashOff,
                        contentDescription = "Torch",
                        tint = if (torchEnabled) Color(0xFFF59E0B) else Color.White
                    )
                }

                Spacer(modifier = Modifier.width(8.dp))

                IconButton(
                    onClick = { showSettingsDialog = true },
                    modifier = Modifier
                        .size(42.dp)
                        .background(Color(0xCC0F172A), CircleShape)
                ) {
                    Icon(
                        imageVector = Icons.Default.Settings,
                        contentDescription = "Settings",
                        tint = Color.White
                    )
                }
            }
        }

        // 2. Bottom Result Card
        AnimatedVisibility(
            visible = streamResult != null && streamResult.containerNumber.isNotEmpty() && streamResult.containerNumber != "Not Found",
            enter = slideInVertically(initialOffsetY = { it }),
            exit = slideOutVertically(targetOffsetY = { it }),
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(16.dp)
        ) {
            val res = streamResult ?: return@AnimatedVisibility

            Card(
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(containerColor = Color(0xF00F172A)),
                elevation = CardDefaults.cardElevation(defaultElevation = 8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(18.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = "IDENTIFIED CONTAINER",
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color(0xFF94A3B8),
                            letterSpacing = 1.sp
                        )

                        // Status Badge
                        val (badgeText, badgeBg, badgeFg) = when {
                            res.isValid && !res.repaired -> Triple("✓ ISO 6346 VALID", Color(0xFF14532D), Color(0xFF4ADE80))
                            res.isValid && res.repaired -> Triple("⚡ AUTO-CORRECTED", Color(0xFF713F12), Color(0xFFFDE047))
                            else -> Triple("✕ MISMATCH", Color(0xFF7F1D1D), Color(0xFFFCA5A5))
                        }

                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = badgeBg
                        ) {
                            Text(
                                text = badgeText,
                                color = badgeFg,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp)
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(6.dp))

                    // Big Container Number
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text(
                            text = res.formattedNumber.ifEmpty { res.containerNumber },
                            fontSize = 24.sp,
                            fontWeight = FontWeight.ExtraBold,
                            fontFamily = FontFamily.Monospace,
                            color = Color.White
                        )

                        IconButton(
                            onClick = {
                                clipboardManager.setText(AnnotatedString(res.containerNumber))
                                Toast.makeText(context, "Copied: ${res.containerNumber}", Toast.LENGTH_SHORT).show()
                            }
                        ) {
                            Icon(Icons.Default.ContentCopy, contentDescription = "Copy", tint = Color(0xFF38BDF8))
                        }
                    }

                    Spacer(modifier = Modifier.height(10.dp))

                    // Details
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Column {
                            Text("CARRIER / OPERATOR", fontSize = 10.sp, color = Color(0xFF94A3B8))
                            Text(res.ownerName.ifEmpty { res.ownerCode }, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color.White)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text("ISO TYPE", fontSize = 10.sp, color = Color(0xFF94A3B8))
                            Text(res.sizeType.ifEmpty { "Standard" }, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = Color.White)
                        }
                    }
                }
            }
        }
    }

    // Settings Dialog
    if (showSettingsDialog) {
        var tempUrl by remember { mutableStateOf(currentServerUrl) }

        AlertDialog(
            onDismissRequest = { showSettingsDialog = false },
            title = { Text("Streaming Server Configuration") },
            text = {
                Column {
                    Text("Enter WebSocket Stream URL:", fontSize = 13.sp)
                    Spacer(modifier = Modifier.height(8.dp))
                    OutlinedTextField(
                        value = tempUrl,
                        onValueChange = { tempUrl = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Quick Presets:", fontSize = 12.sp, color = Color.Gray)
                    Spacer(modifier = Modifier.height(6.dp))
                    PresetChip("USB Reverse (127.0.0.1:8000)") { tempUrl = "ws://127.0.0.1:8000/api/v1/stream" }
                    PresetChip("Android Emulator (10.0.2.2:8000)") { tempUrl = "ws://10.0.2.2:8000/api/v1/stream" }
                    PresetChip("Wi-Fi LAN (192.168.1.21:8000)") { tempUrl = "ws://192.168.1.21:8000/api/v1/stream" }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        onUpdateServerUrl(tempUrl)
                        showSettingsDialog = false
                    }
                ) {
                    Text("Connect")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSettingsDialog = false }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
fun PresetChip(label: String, onClick: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = Color(0xFF1E293B),
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 3.dp)
            .clickable { onClick() }
    ) {
        Text(
            text = label,
            fontSize = 12.sp,
            color = Color(0xFF38BDF8),
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)
        )
    }
}
