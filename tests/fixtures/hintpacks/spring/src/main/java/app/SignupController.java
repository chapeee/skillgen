package app;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;
@Controller
public class SignupController {
  private final UserService users;
  public SignupController(UserService users) { this.users = users; }
  @GetMapping("/signup") public String form() { return "signup"; }
  @PostMapping("/signup") public String submit(@ModelAttribute SignupForm form) { users.create(form); return "redirect:/welcome"; }
}
