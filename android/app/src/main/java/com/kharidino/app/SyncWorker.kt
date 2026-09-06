package com.kharidino.app

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.NetworkType
import androidx.work.WorkerParameters

class SyncWorker(appContext: Context, params: WorkerParameters) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result = try {
        KharidinoRepository(applicationContext).sync()
        Result.success()
    } catch (_: Exception) {
        Result.retry()
    }
}

fun scheduleKharidinoSync(context: Context) {
    val request = androidx.work.OneTimeWorkRequestBuilder<SyncWorker>()
        .setConstraints(androidx.work.Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
        .build()
    androidx.work.WorkManager.getInstance(context).enqueueUniqueWork("kharidino-sync", androidx.work.ExistingWorkPolicy.KEEP, request)
}
