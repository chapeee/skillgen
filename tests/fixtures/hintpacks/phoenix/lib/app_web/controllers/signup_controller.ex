defmodule AppWeb.SignupController do
  use AppWeb, :controller
  alias App.Accounts
  def new(conn, _params), do: render(conn, :new, changeset: Accounts.change_user(%Accounts.User{}))
end
