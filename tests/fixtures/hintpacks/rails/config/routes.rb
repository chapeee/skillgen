Rails.application.routes.draw do
  get "/signup", to: "registrations#new"
  post "/signup", to: "registrations#create"
  resources :projects, only: [:edit, :update]
end
