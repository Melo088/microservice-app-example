package com.elgris.usersapi.api;

import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

import java.util.Collections;
import java.util.Map;

// Real health endpoint used by the Docker HEALTHCHECK. It does not require a
// JWT: JwtAuthenticationFilter lets requests to this path through before
// checking the Authorization header.
@RestController()
@RequestMapping("/health")
public class HealthController {

    @RequestMapping(method = RequestMethod.GET)
    public Map<String, String> health() {
        return Collections.singletonMap("status", "UP");
    }

}
