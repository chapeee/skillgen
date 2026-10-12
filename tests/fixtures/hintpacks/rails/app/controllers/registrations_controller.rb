class RegistrationsController < ApplicationController
  def new
    @user = User.new
  end
  def create
    @user = User.create(params.require(:user).permit(:name, :email))
  end
end
