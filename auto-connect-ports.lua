-- Based on: https://bennett.dev/auto-link-pipewire-ports-wireplumber/
--
-- This script ensures that ONLY the default source/sink are connected to REAPER,
-- and not ALL available sources/sinks.
-- It is an attempt to fix stuttering e.g. https://gitlab.freedesktop.org/pipewire/pipewire/-/issues/2314
--
-- To install:
-- mkdir ~/.config/wireplumber/wireplumber.conf.d
-- Create ~/.config/wireplumber/wireplumber.conf.d/99-auto-connect-ports.conf containing:
-- wireplumber.components = [
--   {
--     name = /path/to/REAPER-plugins/auto-connect-ports.lua, type = script/lua
--     provides = custom.auto-connect-ports
--   }
-- ]
-- wireplumber.profiles = {
--   main = {
--     custom.auto-connect-ports = required
--   }
-- }

cutils = require ("common-utils")

-- Link two ports together
function link_port(output_port, input_port)
  if not input_port or not output_port then
    return nil
  end

  local link_args = {
    ["link.input.node"] = input_port.properties["node.id"],
    ["link.input.port"] = input_port.properties["object.id"],

    ["link.output.node"] = output_port.properties["node.id"],
    ["link.output.port"] = output_port.properties["object.id"],
    
    -- The node never got created if it didn't have this field set to something
    ["object.id"] = nil,

    -- I was running into issues when I didn't have this set
    ["object.linger"] = true,

    ["node.description"] = "Link created by auto_connect_ports"
  }

  local link = Link("link-factory", link_args)
  link:activate(1)

  return link
end

function auto_connect_ports(args)
  local output_om = ObjectManager {
    Interest {
      type = "port",
      Constraint { "port.direction", "equals", "out" }
    }
  }

  local links = {}

  local input_om = ObjectManager {
    Interest {
      type = "port",
      Constraint { "port.direction", "equals", "in" }
    }
  }

  local all_nodes = ObjectManager {
    Interest {
      type = "node",
    }
  }

  function _connect()
    local metadata = cutils.get_default_metadata_object()
    local default_source_name = Json.Raw (metadata:find (0, "default.audio.source")):parse ().name
    local default_sink_name = Json.Raw (metadata:find (0, "default.audio.sink")):parse ().name
    local default_sink_node = all_nodes:lookup { Constraint { "node.name", "equals", default_sink_name } }
    local default_source_node = all_nodes:lookup { Constraint { "node.name", "equals", default_source_name } }
    if not default_sink_node or not default_source_node then
      return
    end
    local default_sink_id = default_sink_node.properties["object.id"]
    local default_source_id = default_source_node.properties["object.id"]
    --print(string.format("%s %s %s %s", default_sink_name, default_sink_id, default_source_name, default_source_id))

    -- Iterate through all the output ports with the correct channel name
    for app_output in output_om:iterate { args.output } do
      local num = tonumber(string.gsub(app_output.properties["port.alias"], "REAPER:out", ""), 10)
      if num then
        local def_input = input_om:lookup { Constraint { "node.id", "equals", tostring(default_sink_id) }, Constraint { "port.id", "equals", tostring(num - 1) } }
        if def_input then
          local link = link_port(app_output, def_input)
          table.insert(links, link)
        end
      end
    end
    for app_input in input_om:iterate { args.input } do
      local num = tonumber(string.gsub(app_input.properties["port.alias"], "REAPER:in", ""), 10)
      if num then
        local def_output = output_om:lookup { Constraint { "node.id", "equals", tostring(default_source_id) }, Constraint { "port.id", "equals", tostring(num - 1) } }
        --print(string.format("node.id %s port.id %s", tostring(default_source_id), tostring(app_input.properties["port.id"])))
        if def_output then
          local link = link_port(def_output, app_input)
          table.insert(links, link)
        end
      end
    end
  end

  SimpleEventHook {
    name = "rav/default-change",
    interests = {
      EventInterest {
        Constraint { "event.type", "=", "metadata-changed" },
        Constraint { "metadata.name", "=", "default" },
        Constraint { "event.subject.key", "c", "default.audio.source", "default.audio.sink" },
      },
    },
    execute = function (event)
      _connect()
    end
  }:register ()

  output_om:connect("object-added", _connect)
  input_om:connect("object-added", _connect)

  output_om:activate()
  input_om:activate()
  all_nodes:activate()
end

auto_connect_ports {
  output = Constraint { "object.path", "matches", "REAPER:*" },
  input = Constraint { "object.path", "matches", "REAPER:*" },
}
