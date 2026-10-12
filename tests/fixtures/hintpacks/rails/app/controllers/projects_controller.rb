class ProjectsController < ApplicationController
  def edit
    @project = Project.find(params[:id])
  end
  def update
    Project.find(params[:id]).update(params.require(:project).permit(:name))
  end
end
