package com.ada.shared.observability

@Target(AnnotationTarget.CLASS)
@Retention(AnnotationRetention.RUNTIME)
annotation class MeasuredContextItem(val component: String)
