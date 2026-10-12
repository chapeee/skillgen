defmodule AppWeb.ContactLive do
  use AppWeb, :live_view
  def render(assigns), do: ~H"<.form for={@form}><.input field={@form[:message]} /></.form>"
end
