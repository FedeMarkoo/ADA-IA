package com.ada

import org.springframework.boot.autoconfigure.SpringBootApplication
import org.springframework.boot.runApplication

@SpringBootApplication
class AdaApplication

fun main(args: Array<String>) {
    runApplication<AdaApplication>(*args)
}
