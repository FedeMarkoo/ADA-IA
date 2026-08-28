package com.ada.conversation.infrastructure.in.rest;

import org.springframework.web.bind.annotation.*;
@RestController public class HealthController { @GetMapping("/health") public String health(){return "UP";} }
