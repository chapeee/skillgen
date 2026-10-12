package app;
import jakarta.validation.constraints.*;
public class SignupForm { @NotBlank public String name; @Email public String email; }
