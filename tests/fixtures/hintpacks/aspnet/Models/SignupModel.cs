using System.ComponentModel.DataAnnotations;
namespace App.Models { public class SignupModel { [Required] public string Name { get; set; } [EmailAddress] public string Email { get; set; } } }
