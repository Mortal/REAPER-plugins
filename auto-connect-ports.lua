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

-- Goal: REAPER's first input/output ports
-- should be linked to the default source/sink ports.
-- The default sink monitor L/R should be linked to the REAPER's input 19-20.
-- The Blue Yeti microphone input should be linked to REAPER's input 11-12.

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
      args["output"],
      Constraint { "port.direction", "equals", "out" }
    }
  }

  local links = {}

  local input_om = ObjectManager {
    Interest {
      type = "port",
      args["input"],
      Constraint { "port.direction", "equals", "in" }
    }
  }

  local all_links = ObjectManager {
    Interest {
      type = "link",
    }
  }

  function _connect()
    if delete_links then
      for _i, link in pairs(links) do
        link:request_destroy()
      end

      links = {}

      return
    end

    for output_name, input_names in pairs(args.connect) do
      local input_names = input_names[1] == nil and { input_names } or input_names

      if delete_links then
      else
        -- Iterate through all the output ports with the correct channel name
        for output in output_om:iterate { Constraint { "port.alias", "equals", output_name } } do

          for _i, input_name in pairs(input_names) do
            -- Iterate through all the input ports with the correct channel name
            for input in input_om:iterate { Constraint { "port.alias", "equals", input_name } } do
              -- Link all the nodes
              local link = link_port(output, input)

              if link then
                table.insert(links, link)
              end
            end
          end
        end
      end
    end
  end

  output_om:connect("object-added", _connect)
  input_om:connect("object-added", _connect)
  all_links:connect("object-added", _connect)

  output_om:activate()
  input_om:activate()
  all_links:activate()
end

function auto_connect_default_sink(args)
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
    if not metadata then
      print("No metadata")
      return
    end
    local default_sink_json = metadata:find (0, "default.audio.sink")
    if not default_sink_json then
      --print("No default sink")
      return
    end
    local default_sink_name = Json.Raw (default_sink_json):parse ().name
    if not default_sink_name then
      print("No default sink name")
      return
    end
    local default_sink_node = all_nodes:lookup { Constraint { "node.name", "equals", default_sink_name } }
    if not default_sink_node then
      --print("Did not find default sink")
      return
    end
    local default_sink_id = default_sink_node.properties["object.id"]
    --print(string.format("Found default sink %s %s", default_sink_name, default_sink_id))

    -- Iterate through all the output ports with the correct channel name
    for app_port in output_om:iterate { Constraint { "port.alias", "matches", args.port_alias_prefix .. "*" } } do
      local num = tonumber(string.gsub(app_port.properties["port.alias"], args.port_alias_prefix, ""), 10)
      if num then
        local def_input = input_om:lookup { Constraint { "node.id", "equals", tostring(default_sink_id) }, Constraint { "port.id", "equals", tostring(num - 1) } }
        if def_input then
          local link = link_port(app_port, def_input)
          --print("link sink", app_port, def_input, link)
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
        Constraint { "event.subject.key", "=", "default.audio.sink" },
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

function auto_connect_default_source(args)
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
    if not metadata then
      print("No metadata")
      return
    end
    local default_source_json = metadata:find (0, "default.audio.source")
    if not default_source_json then
      --print("No default source")
      return
    end
    local default_source_name = Json.Raw (default_source_json):parse ().name
    if not default_source_name then
      print("No default source name")
      return
    end
    local default_source_node = all_nodes:lookup { Constraint { "node.name", "equals", default_source_name } }
    if not default_source_node then
      --print("Did not find default source")
      return
    end
    local default_source_id = default_source_node.properties["object.id"]
    --print(string.format("Found default source %s %s", default_source_name, default_source_id))

    -- Iterate through all the output ports with the correct channel name
    for app_port in input_om:iterate { Constraint { "port.alias", "matches", args.port_alias_prefix .. "*" } } do
      local num = tonumber(string.gsub(app_port.properties["port.alias"], args.port_alias_prefix, ""), 10)
      if num then
        local def_output = output_om:lookup { Constraint { "node.id", "equals", tostring(default_source_id) }, Constraint { "port.id", "equals", tostring(num - 1) } }
        --print(string.format("node.id %s port.id %s", tostring(default_source_id), tostring(app_port.properties["port.id"])))
        if def_output then
          local link = link_port(def_output, app_port)
          --print("link source", def_output, app_port, link)
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
        Constraint { "event.subject.key", "=", "default.audio.source" },
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

function auto_connect_default_sink_monitor(args)
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
    if not metadata then
      print("No metadata")
      return
    end
    local default_sink_json = metadata:find (0, "default.audio.sink")
    if not default_sink_json then
      --print("No default sink")
      return
    end
    local default_sink_name = Json.Raw (default_sink_json):parse ().name
    if not default_sink_name then
      print("No default sink name")
      return
    end
    local default_sink_node = all_nodes:lookup { Constraint { "node.name", "equals", default_sink_name } }
    if not default_sink_node then
      --print("Did not find default sink")
      return
    end
    local default_sink_id = default_sink_node.properties["object.id"]
    print(string.format("Found default sink monitor %s %s", default_sink_name, default_sink_id))

    for app_port in input_om:iterate { Constraint { "port.alias", "=", args.port_alias_1 } } do
      local def_output = output_om:lookup { Constraint { "node.id", "equals", tostring(default_sink_id) }, Constraint { "port.id", "equals", 0 } }
      print(string.format("node.id %s port.id %s", tostring(default_sink_id), tostring(app_port.properties["port.id"])))
      if def_output then
        local link = link_port(def_output, app_port)
        print("link source", def_output, app_port, link)
        table.insert(links, link)
      end
    end
    for app_port in input_om:iterate { Constraint { "port.alias", "=", args.port_alias_2 } } do
      local def_output = output_om:lookup { Constraint { "node.id", "equals", tostring(default_sink_id) }, Constraint { "port.id", "equals", 1 } }
      print(string.format("node.id %s port.id %s", tostring(default_sink_id), tostring(app_port.properties["port.id"])))
      if def_output then
        local link = link_port(def_output, app_port)
        print("link source", def_output, app_port, link)
        table.insert(links, link)
      end
    end
  end

  SimpleEventHook {
    name = "rav/default-change",
    interests = {
      EventInterest {
        Constraint { "event.type", "=", "metadata-changed" },
        Constraint { "metadata.name", "=", "default" },
        Constraint { "event.subject.key", "=", "default.audio.source" },
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
  output = Constraint { "port.alias", "matches", "Blue Microphones:capture_*" },
  input = Constraint { "port.alias", "matches", "REAPER:in*" },
  connect = {
    ["Blue Microphones:capture_FL"] = "REAPER:in11",
    ["Blue Microphones:capture_FR"] = "REAPER:in12",
  }
}
auto_connect_default_source {
  port_alias_prefix = "REAPER:in",
}
auto_connect_default_sink {
  port_alias_prefix = "REAPER:out",
}
auto_connect_default_sink_monitor {
  port_alias_1 = "REAPER:in19",
  port_alias_2 = "REAPER:in20",
}
