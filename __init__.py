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


from .prefs.properties import register_properties, unregister_properties
from .main.operators import register_operators, unregister_operators
from .prefs.panel import register_panel, unregister_panel

def register():
	register_properties()
	register_operators()
	register_panel()
	
def unregister():
	unregister_panel()
	unregister_operators()
	unregister_properties()
