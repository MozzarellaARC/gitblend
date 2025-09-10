# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


from . import main as main_module
from . import prefs as prefs_module

def register():
	prefs_module.register_properties()
	prefs_module.register_panel()
	main_module.register_operators()

def unregister():
	main_module.unregister_operators()
	prefs_module.unregister_panel()
	prefs_module.unregister_properties()
