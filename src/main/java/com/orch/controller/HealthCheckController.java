package com.orch.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.Map;

@RestController
public class HealthCheckController {

    @GetMapping("/healthcheck")
    public Map<String, Object> healthcheck() {
        return Map.of(
                "status", "UP",
                "timestamp", Instant.now().toString(),
                "service", "orch-app",
                "version", "0.0.1-SNAPSHOT"
        );
    }
}
