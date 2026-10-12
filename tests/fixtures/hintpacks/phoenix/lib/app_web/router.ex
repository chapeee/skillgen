defmodule AppWeb.Router do
  use AppWeb, :router
  scope "/", AppWeb do
    get "/signup", SignupController, :new
    live "/contact", ContactLive
  end
end
