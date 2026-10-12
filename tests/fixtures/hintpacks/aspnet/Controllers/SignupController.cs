using Microsoft.AspNetCore.Mvc;
namespace App.Controllers {
  [Route("signup")]
  public class SignupController : Controller {
    [HttpGet("")] public IActionResult Index() => View(new SignupModel());
    [HttpPost("")] public IActionResult Create(SignupModel model) => Redirect("/welcome");
  }
}
